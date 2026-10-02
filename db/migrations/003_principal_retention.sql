BEGIN;
SET LOCAL ROLE flamoris_ai_owner;

-- Retain conversation provenance/fences; retire only short-lived authorization.
CREATE INDEX IF NOT EXISTS conversations_principal_session_idx
    ON chat.conversations ((metadata->>'principal_session'))
    WHERE metadata ? 'principal_session';

CREATE OR REPLACE FUNCTION chat.principal_session_retirable(binding UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY INVOKER
SET search_path = pg_catalog AS $$
    SELECT EXISTS (
        SELECT 1 FROM chat.principal_sessions s
        WHERE s.id = binding AND s.expires_at <= statement_timestamp() - INTERVAL '1 hour'
          AND NOT EXISTS (
            SELECT 1 FROM chat.conversations c
            WHERE c.metadata ? 'principal_session'
              AND c.metadata->>'principal_session' = s.id::text
              AND (c.status IS DISTINCT FROM 'closed' OR c.ended_at IS NULL
                   OR c.ended_at > statement_timestamp() - INTERVAL '1 hour'
                   OR EXISTS (
                     SELECT 1 FROM chat.conversation_sessions cs
                     JOIN runtime.instances i ON i.id = cs.instance_id
                     WHERE cs.conversation_id = c.id
                       AND (cs.left_at IS NULL OR i.ended_at IS NULL
                            OR cs.left_at > statement_timestamp() - INTERVAL '1 hour'
                            OR i.ended_at > statement_timestamp() - INTERVAL '1 hour')
                   ))
          )
    );
$$;

CREATE OR REPLACE FUNCTION chat.guard_principal_session_retention()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF NOT chat.principal_session_retirable(OLD.id) THEN
            RAISE EXCEPTION 'principal session retention blocked';
        END IF;
        RETURN OLD;
    END IF;
    -- A historical scoped UUID must never be re-established with new authority.
    IF EXISTS (
        SELECT 1 FROM chat.conversations c
        WHERE c.metadata ? 'principal_session'
          AND c.metadata->>'principal_session' = NEW.id::text
    ) THEN
        RAISE EXCEPTION 'historical principal session cannot be reused';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS principal_session_retention ON chat.principal_sessions;
CREATE TRIGGER principal_session_retention BEFORE INSERT OR DELETE ON chat.principal_sessions
    FOR EACH ROW EXECUTE FUNCTION chat.guard_principal_session_retention();

CREATE OR REPLACE FUNCTION chat.retire_principal_sessions(batch_size INTEGER DEFAULT 32)
RETURNS INTEGER LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog AS $$
DECLARE
    retired INTEGER;
BEGIN
    IF batch_size IS NULL OR batch_size < 1 OR batch_size > 128 THEN
        RAISE EXCEPTION 'invalid principal retention batch';
    END IF;
    -- Same namespace lock as PrincipalSessions.open; wait is bounded for operators.
    IF NOT pg_try_advisory_xact_lock(1179402567, 18) THEN
        RAISE EXCEPTION 'principal namespace busy';
    END IF;
    WITH candidates AS MATERIALIZED (
        SELECT s.id FROM chat.principal_sessions s
        WHERE chat.principal_session_retirable(s.id)
        ORDER BY s.expires_at, s.id
        LIMIT batch_size FOR UPDATE OF s SKIP LOCKED
    )
    DELETE FROM chat.principal_sessions s USING candidates c WHERE s.id = c.id;
    GET DIAGNOSTICS retired = ROW_COUNT;
    RETURN retired;
END;
$$;

-- Helpers run via triggers for ordinary runtime INSERT; they grant no mutation.
REVOKE ALL ON FUNCTION chat.retire_principal_sessions(INTEGER)
    FROM PUBLIC, flamoris_ai_app;
GRANT EXECUTE ON FUNCTION chat.retire_principal_sessions(INTEGER) TO flamoris_ai_owner;
REVOKE DELETE ON chat.principal_sessions FROM flamoris_ai_app;

INSERT INTO core.schema_migrations(version, description)
VALUES ('003_principal_retention', 'Bounded owner retirement preserving history and request fences')
ON CONFLICT (version) DO NOTHING;

COMMIT;
