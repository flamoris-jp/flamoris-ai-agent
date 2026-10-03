BEGIN;
SET LOCAL ROLE flamoris_ai_owner;

CREATE TABLE IF NOT EXISTS core.personality_grants (
    delegator_key TEXT NOT NULL,
    human_id UUID NOT NULL REFERENCES core.humans(id) ON DELETE RESTRICT,
    agent_id UUID NOT NULL REFERENCES core.agents(id) ON DELETE RESTRICT,
    can_read BOOLEAN NOT NULL DEFAULT FALSE,
    can_edit BOOLEAN NOT NULL DEFAULT FALSE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (delegator_key, human_id, agent_id),
    CHECK (NOT can_edit OR can_read)
);
CREATE TABLE IF NOT EXISTS core.agent_personalities (
    agent_id UUID PRIMARY KEY REFERENCES core.agents(id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL CHECK (revision BETWEEN 1 AND 256)
);
CREATE TABLE IF NOT EXISTS core.personality_versions (
    agent_id UUID NOT NULL REFERENCES core.agents(id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL CHECK (revision BETWEEN 1 AND 256),
    display_name TEXT NOT NULL CHECK (length(display_name) BETWEEN 1 AND 128),
    sections JSONB NOT NULL CHECK (jsonb_typeof(sections) = 'array'),
    request_id UUID NOT NULL,
    request_digest TEXT NOT NULL CHECK (length(request_digest) = 64),
    updated_by UUID REFERENCES core.humans(id) ON DELETE RESTRICT,
    delegator_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (agent_id, revision),
    UNIQUE (agent_id, request_id)
);
CREATE TABLE IF NOT EXISTS core.model_grants (
    delegator_key TEXT NOT NULL,
    human_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    project_id UUID NOT NULL,
    model_id UUID NOT NULL REFERENCES runtime.models(id) ON DELETE RESTRICT,
    allow_remote BOOLEAN NOT NULL DEFAULT FALSE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (delegator_key, human_id, agent_id, project_id, model_id),
    FOREIGN KEY (delegator_key, human_id, agent_id, project_id)
      REFERENCES core.principal_grants(delegator_key, human_id, agent_id, project_id)
      ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS chat.principal_options (
    session_id UUID PRIMARY KEY REFERENCES chat.principal_sessions(id) ON DELETE CASCADE,
    public_model_id TEXT NOT NULL,
    target_digest TEXT NOT NULL CHECK (length(target_digest) = 64),
    model_id UUID NOT NULL REFERENCES runtime.models(id) ON DELETE RESTRICT,
    remote_consent BOOLEAN NOT NULL,
    data_flow TEXT NOT NULL CHECK (data_flow IN ('local_only', 'remote_authorized'))
);
REVOKE ALL ON core.personality_grants, core.model_grants FROM flamoris_ai_app;
GRANT SELECT ON core.personality_grants, core.model_grants TO flamoris_ai_app;
REVOKE ALL ON core.personality_versions, core.agent_personalities, chat.principal_options FROM flamoris_ai_app;
GRANT SELECT, INSERT ON core.personality_versions, chat.principal_options TO flamoris_ai_app;
GRANT SELECT, INSERT, UPDATE ON core.agent_personalities TO flamoris_ai_app;

INSERT INTO core.schema_migrations(version, description)
VALUES ('004_assistant_settings', 'Agent-owned personality revisions and immutable model session options')
ON CONFLICT (version) DO NOTHING;
COMMIT;
