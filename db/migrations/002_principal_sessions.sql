BEGIN;
SET LOCAL ROLE flamoris_ai_owner;

-- Operator-controlled delegation grants. No request may create its own grant.
CREATE TABLE IF NOT EXISTS core.principal_grants (
    delegator_key TEXT NOT NULL CHECK (delegator_key ~ '^[A-Za-z0-9_-]{1,64}$'),
    human_id UUID NOT NULL REFERENCES core.humans(id) ON DELETE RESTRICT,
    agent_id UUID NOT NULL REFERENCES core.agents(id) ON DELETE RESTRICT,
    project_id UUID NOT NULL REFERENCES core.projects(id) ON DELETE RESTRICT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (delegator_key, human_id, agent_id, project_id)
);

CREATE TABLE IF NOT EXISTS chat.principal_sessions (
    id UUID PRIMARY KEY,
    delegator_key TEXT NOT NULL,
    human_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    project_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    FOREIGN KEY (delegator_key, human_id, agent_id, project_id)
        REFERENCES core.principal_grants(delegator_key, human_id, agent_id, project_id)
        ON DELETE RESTRICT,
    CHECK (expires_at > created_at AND expires_at <= created_at + INTERVAL '1 hour')
);

CREATE INDEX IF NOT EXISTS principal_sessions_expiry_idx
    ON chat.principal_sessions(expires_at);

-- Baseline default privileges permit core DML; grants must remain operator-only.
REVOKE INSERT, UPDATE, DELETE ON core.principal_grants FROM flamoris_ai_app;
GRANT SELECT ON core.principal_grants TO flamoris_ai_app;
REVOKE DELETE ON chat.principal_sessions FROM flamoris_ai_app;
GRANT SELECT, INSERT, UPDATE ON chat.principal_sessions TO flamoris_ai_app;

CREATE OR REPLACE FUNCTION chat.immutable_principal_session()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF ROW(NEW.id, NEW.delegator_key, NEW.human_id, NEW.agent_id, NEW.project_id,
           NEW.created_at, NEW.expires_at)
       IS DISTINCT FROM
       ROW(OLD.id, OLD.delegator_key, OLD.human_id, OLD.agent_id, OLD.project_id,
           OLD.created_at, OLD.expires_at)
       OR (OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at)
    THEN
        RAISE EXCEPTION 'immutable principal session';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS principal_session_immutable ON chat.principal_sessions;
CREATE TRIGGER principal_session_immutable BEFORE UPDATE ON chat.principal_sessions
    FOR EACH ROW EXECUTE FUNCTION chat.immutable_principal_session();

INSERT INTO core.schema_migrations(version, description)
VALUES ('002_principal_sessions', 'Explicit delegation grants and immutable principal sessions')
ON CONFLICT (version) DO NOTHING;

COMMIT;
