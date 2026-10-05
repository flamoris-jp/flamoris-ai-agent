BEGIN;
SET LOCAL ROLE flamoris_ai_owner;

CREATE TABLE IF NOT EXISTS chat.principal_continuations (
    session_id UUID PRIMARY KEY REFERENCES chat.principal_sessions(id) ON DELETE CASCADE,
    parent_session_id UUID NOT NULL REFERENCES chat.principal_sessions(id) ON DELETE RESTRICT,
    request_id UUID NOT NULL,
    UNIQUE (parent_session_id),
    CHECK (session_id <> parent_session_id)
);
REVOKE ALL ON chat.principal_continuations FROM flamoris_ai_app;
GRANT SELECT, INSERT ON chat.principal_continuations TO flamoris_ai_app;

-- Retire eligible leaves first; never erase an ancestor of a live continuation.
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
          AND NOT EXISTS (SELECT 1 FROM chat.principal_continuations p
                          WHERE p.parent_session_id = s.id)
        ORDER BY s.expires_at, s.id
        LIMIT batch_size FOR UPDATE OF s SKIP LOCKED
    )
    DELETE FROM chat.principal_sessions s USING candidates c WHERE s.id = c.id;
    GET DIAGNOSTICS retired = ROW_COUNT;
    RETURN retired;
END;
$$;


INSERT INTO core.schema_migrations(version, description)
VALUES ('005_model_continuations', 'Explicit immutable model-session continuation lineage')
ON CONFLICT (version) DO NOTHING;
COMMIT;
