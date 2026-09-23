-- ============================================================================
-- FLAMORIS AI v0.1
-- Database: flamoris_ai
-- Owner role: flamoris_ai_owner
-- Runtime role: flamoris_ai_app
--
-- Run this while connected to database "flamoris_ai" as PostgreSQL superuser.
-- ============================================================================

SET ROLE flamoris_ai_owner;

CREATE SCHEMA IF NOT EXISTS core    AUTHORIZATION flamoris_ai_owner;
CREATE SCHEMA IF NOT EXISTS runtime AUTHORIZATION flamoris_ai_owner;
CREATE SCHEMA IF NOT EXISTS chat    AUTHORIZATION flamoris_ai_owner;
CREATE SCHEMA IF NOT EXISTS memory  AUTHORIZATION flamoris_ai_owner;
CREATE SCHEMA IF NOT EXISTS relay   AUTHORIZATION flamoris_ai_owner;
CREATE SCHEMA IF NOT EXISTS ops     AUTHORIZATION flamoris_ai_owner;

-- --------------------------------------------------------------------------
-- Common helper
-- --------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION core.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

-- --------------------------------------------------------------------------
-- Schema migrations
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS core.schema_migrations (
    version         TEXT PRIMARY KEY,
    description     TEXT NOT NULL,
    applied_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- --------------------------------------------------------------------------
-- Projects
-- Multi-level hierarchy using parent_project_id.
-- project_key is a stable, globally unique application key.
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS core.projects (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_project_id   UUID REFERENCES core.projects(id) ON DELETE RESTRICT,
    project_key         TEXT NOT NULL UNIQUE,
    slug                TEXT NOT NULL,
    name                TEXT NOT NULL,
    project_type        TEXT NOT NULL DEFAULT 'project',
    status              TEXT NOT NULL DEFAULT 'active',
    description         TEXT,
    sort_order          INTEGER NOT NULL DEFAULT 0,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (parent_project_id IS NULL OR parent_project_id <> id)
);

CREATE UNIQUE INDEX IF NOT EXISTS projects_root_slug_uq
    ON core.projects (slug)
    WHERE parent_project_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS projects_child_slug_uq
    ON core.projects (parent_project_id, slug)
    WHERE parent_project_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS projects_parent_idx
    ON core.projects (parent_project_id);

CREATE OR REPLACE FUNCTION core.prevent_project_cycle()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.parent_project_id IS NULL THEN
        RETURN NEW;
    END IF;

    IF NEW.parent_project_id = NEW.id THEN
        RAISE EXCEPTION 'A project cannot be its own parent';
    END IF;

    IF EXISTS (
        WITH RECURSIVE ancestors AS (
            SELECT p.id, p.parent_project_id
            FROM core.projects AS p
            WHERE p.id = NEW.parent_project_id

            UNION ALL

            SELECT p.id, p.parent_project_id
            FROM core.projects AS p
            JOIN ancestors AS a
              ON p.id = a.parent_project_id
        )
        SELECT 1
        FROM ancestors
        WHERE id = NEW.id
    ) THEN
        RAISE EXCEPTION 'Project hierarchy cycle detected';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_projects_no_cycle ON core.projects;
CREATE TRIGGER trg_projects_no_cycle
BEFORE INSERT OR UPDATE OF parent_project_id
ON core.projects
FOR EACH ROW
EXECUTE FUNCTION core.prevent_project_cycle();

DROP TRIGGER IF EXISTS trg_projects_updated_at ON core.projects;
CREATE TRIGGER trg_projects_updated_at
BEFORE UPDATE ON core.projects
FOR EACH ROW
EXECUTE FUNCTION core.set_updated_at();

-- A convenient recursive view showing full project paths.
CREATE OR REPLACE VIEW core.project_paths AS
WITH RECURSIVE project_tree AS (
    SELECT
        p.id,
        p.parent_project_id,
        p.project_key,
        p.slug,
        p.name,
        p.project_type,
        p.status,
        0 AS depth,
        ARRAY[p.id] AS id_path,
        ARRAY[p.slug] AS slug_path,
        ARRAY[p.name] AS name_path
    FROM core.projects AS p
    WHERE p.parent_project_id IS NULL

    UNION ALL

    SELECT
        c.id,
        c.parent_project_id,
        c.project_key,
        c.slug,
        c.name,
        c.project_type,
        c.status,
        t.depth + 1,
        t.id_path || c.id,
        t.slug_path || c.slug,
        t.name_path || c.name
    FROM core.projects AS c
    JOIN project_tree AS t
      ON c.parent_project_id = t.id
)
SELECT
    id,
    parent_project_id,
    project_key,
    slug,
    name,
    project_type,
    status,
    depth,
    id_path,
    slug_path,
    name_path,
    array_to_string(slug_path, '/') AS slug_path_text,
    array_to_string(name_path, ' / ') AS name_path_text
FROM project_tree;

-- --------------------------------------------------------------------------
-- Humans and Agents
-- Agent identity is stable even when the model changes.
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS core.humans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    human_key       TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.agents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_key           TEXT NOT NULL UNIQUE,
    display_name        TEXT NOT NULL,
    agent_type          TEXT NOT NULL DEFAULT 'agent',
    default_project_id  UUID REFERENCES core.projects(id) ON DELETE SET NULL,
    enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.agent_projects (
    agent_id        UUID NOT NULL REFERENCES core.agents(id) ON DELETE CASCADE,
    project_id      UUID NOT NULL REFERENCES core.projects(id) ON DELETE CASCADE,
    project_role    TEXT NOT NULL DEFAULT 'member',
    inherit_parent  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (agent_id, project_id)
);

DROP TRIGGER IF EXISTS trg_humans_updated_at ON core.humans;
CREATE TRIGGER trg_humans_updated_at
BEFORE UPDATE ON core.humans
FOR EACH ROW
EXECUTE FUNCTION core.set_updated_at();

DROP TRIGGER IF EXISTS trg_agents_updated_at ON core.agents;
CREATE TRIGGER trg_agents_updated_at
BEFORE UPDATE ON core.agents
FOR EACH ROW
EXECUTE FUNCTION core.set_updated_at();

-- --------------------------------------------------------------------------
-- Runtime
-- hosts = machine/VM/container/mobile
-- applications = software identity
-- models = model identity
-- instances = one concrete running process/session
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS runtime.hosts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_host_id  UUID REFERENCES runtime.hosts(id) ON DELETE SET NULL,
    host_key        TEXT NOT NULL UNIQUE,
    hostname        TEXT,
    display_name    TEXT NOT NULL,
    host_type       TEXT NOT NULL DEFAULT 'machine',
    os_name         TEXT,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (parent_host_id IS NULL OR parent_host_id <> id)
);

CREATE TABLE IF NOT EXISTS runtime.applications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_key TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    app_type        TEXT NOT NULL DEFAULT 'application',
    version         TEXT,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runtime.models (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_key       TEXT NOT NULL UNIQUE,
    provider        TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    base_model_name TEXT,
    version         TEXT,
    context_window  INTEGER,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runtime.instances (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    host_id         UUID NOT NULL REFERENCES runtime.hosts(id) ON DELETE RESTRICT,
    application_id  UUID NOT NULL REFERENCES runtime.applications(id) ON DELETE RESTRICT,
    agent_id        UUID REFERENCES core.agents(id) ON DELETE SET NULL,
    model_id        UUID REFERENCES runtime.models(id) ON DELETE SET NULL,
    instance_label  TEXT,
    process_id      INTEGER,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at        TIMESTAMPTZ,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE INDEX IF NOT EXISTS instances_host_idx
    ON runtime.instances (host_id, started_at DESC);

CREATE INDEX IF NOT EXISTS instances_agent_idx
    ON runtime.instances (agent_id, started_at DESC);

CREATE INDEX IF NOT EXISTS instances_application_idx
    ON runtime.instances (application_id, started_at DESC);

DROP TRIGGER IF EXISTS trg_hosts_updated_at ON runtime.hosts;
CREATE TRIGGER trg_hosts_updated_at
BEFORE UPDATE ON runtime.hosts
FOR EACH ROW
EXECUTE FUNCTION core.set_updated_at();

DROP TRIGGER IF EXISTS trg_applications_updated_at ON runtime.applications;
CREATE TRIGGER trg_applications_updated_at
BEFORE UPDATE ON runtime.applications
FOR EACH ROW
EXECUTE FUNCTION core.set_updated_at();

DROP TRIGGER IF EXISTS trg_models_updated_at ON runtime.models;
CREATE TRIGGER trg_models_updated_at
BEFORE UPDATE ON runtime.models
FOR EACH ROW
EXECUTE FUNCTION core.set_updated_at();

-- --------------------------------------------------------------------------
-- Chat
-- A conversation can have multiple agents/humans and multiple runtime sessions.
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS chat.conversations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID REFERENCES core.projects(id) ON DELETE SET NULL,
    primary_agent_id    UUID REFERENCES core.agents(id) ON DELETE SET NULL,
    title               TEXT,
    status              TEXT NOT NULL DEFAULT 'open',
    system_prompt       TEXT,
    system_context      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at            TIMESTAMPTZ,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (ended_at IS NULL OR ended_at >= created_at)
);

CREATE TABLE IF NOT EXISTS chat.participants (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID NOT NULL REFERENCES chat.conversations(id) ON DELETE CASCADE,
    human_id            UUID REFERENCES core.humans(id) ON DELETE SET NULL,
    agent_id            UUID REFERENCES core.agents(id) ON DELETE SET NULL,
    display_name        TEXT NOT NULL,
    joined_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    left_at             TIMESTAMPTZ,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (conversation_id, id),
    CHECK (
        (human_id IS NOT NULL AND agent_id IS NULL)
        OR
        (human_id IS NULL AND agent_id IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS chat.conversation_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID NOT NULL REFERENCES chat.conversations(id) ON DELETE CASCADE,
    instance_id         UUID NOT NULL REFERENCES runtime.instances(id) ON DELETE RESTRICT,
    joined_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    left_at             TIMESTAMPTZ,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (left_at IS NULL OR left_at >= joined_at)
);

CREATE TABLE IF NOT EXISTS chat.messages (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ordinal                 BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    conversation_id         UUID NOT NULL REFERENCES chat.conversations(id) ON DELETE CASCADE,
    sender_participant_id   UUID,
    role                    TEXT NOT NULL,
    content                 TEXT NOT NULL,
    origin_instance_id      UUID REFERENCES runtime.instances(id) ON DELETE SET NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,
    FOREIGN KEY (conversation_id, sender_participant_id)
        REFERENCES chat.participants(conversation_id, id)
        ON DELETE SET NULL,
    CHECK (role IN ('user', 'assistant', 'system', 'tool', 'event'))
);

CREATE INDEX IF NOT EXISTS conversations_project_idx
    ON chat.conversations (project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS conversations_agent_idx
    ON chat.conversations (primary_agent_id, created_at DESC);

CREATE INDEX IF NOT EXISTS participants_conversation_idx
    ON chat.participants (conversation_id);

CREATE INDEX IF NOT EXISTS conversation_sessions_conversation_idx
    ON chat.conversation_sessions (conversation_id, joined_at);

CREATE INDEX IF NOT EXISTS messages_conversation_idx
    ON chat.messages (conversation_id, ordinal);

CREATE INDEX IF NOT EXISTS messages_origin_instance_idx
    ON chat.messages (origin_instance_id, ordinal);

-- --------------------------------------------------------------------------
-- Memory / Knowledge
-- knowledge_items = curated facts / documents / project knowledge
-- memories = agent-experienced memories derived from conversations/events
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memory.knowledge_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID REFERENCES core.projects(id) ON DELETE SET NULL,
    owner_agent_id      UUID REFERENCES core.agents(id) ON DELETE SET NULL,
    title               TEXT,
    content             TEXT NOT NULL,
    knowledge_type      TEXT NOT NULL DEFAULT 'fact',
    source_type         TEXT,
    source_ref          TEXT,
    status              TEXT NOT NULL DEFAULT 'active',
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memory.knowledge_grants (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_id        UUID NOT NULL REFERENCES memory.knowledge_items(id) ON DELETE CASCADE,
    grantee_scope       TEXT NOT NULL,
    grantee_agent_id    UUID REFERENCES core.agents(id) ON DELETE CASCADE,
    grantee_project_id  UUID REFERENCES core.projects(id) ON DELETE CASCADE,
    can_read            BOOLEAN NOT NULL DEFAULT TRUE,
    can_write           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (grantee_scope = 'global'
            AND grantee_agent_id IS NULL
            AND grantee_project_id IS NULL)
        OR
        (grantee_scope = 'agent'
            AND grantee_agent_id IS NOT NULL
            AND grantee_project_id IS NULL)
        OR
        (grantee_scope = 'project'
            AND grantee_agent_id IS NULL
            AND grantee_project_id IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS memory.memories (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_agent_id          UUID NOT NULL REFERENCES core.agents(id) ON DELETE CASCADE,
    project_id              UUID REFERENCES core.projects(id) ON DELETE SET NULL,
    source_conversation_id  UUID REFERENCES chat.conversations(id) ON DELETE SET NULL,
    source_message_id       UUID REFERENCES chat.messages(id) ON DELETE SET NULL,
    memory_type             TEXT NOT NULL DEFAULT 'episodic',
    content                 TEXT NOT NULL,
    importance              NUMERIC(4,3) NOT NULL DEFAULT 0.500,
    visibility              TEXT NOT NULL DEFAULT 'private',
    status                  TEXT NOT NULL DEFAULT 'active',
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_accessed_at        TIMESTAMPTZ,
    CHECK (importance >= 0 AND importance <= 1),
    CHECK (visibility IN ('private', 'project', 'shared'))
);

CREATE TABLE IF NOT EXISTS memory.memory_shares (
    memory_id        UUID NOT NULL REFERENCES memory.memories(id) ON DELETE CASCADE,
    agent_id         UUID NOT NULL REFERENCES core.agents(id) ON DELETE CASCADE,
    can_write        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (memory_id, agent_id)
);

-- Metadata for embedding backends. Actual vector storage comes in a later migration.
CREATE TABLE IF NOT EXISTS memory.embedding_models (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_key       TEXT NOT NULL UNIQUE,
    provider        TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    dimensions      INTEGER,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS knowledge_project_idx
    ON memory.knowledge_items (project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS knowledge_owner_agent_idx
    ON memory.knowledge_items (owner_agent_id, created_at DESC);

CREATE INDEX IF NOT EXISTS memories_agent_idx
    ON memory.memories (owner_agent_id, created_at DESC);

CREATE INDEX IF NOT EXISTS memories_project_idx
    ON memory.memories (project_id, created_at DESC);

DROP TRIGGER IF EXISTS trg_knowledge_updated_at ON memory.knowledge_items;
CREATE TRIGGER trg_knowledge_updated_at
BEFORE UPDATE ON memory.knowledge_items
FOR EACH ROW
EXECUTE FUNCTION core.set_updated_at();

-- --------------------------------------------------------------------------
-- Relay
-- correlation_id groups a chain of related events.
-- causation_event_id records which event directly caused another event.
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS relay.events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID REFERENCES core.projects(id) ON DELETE SET NULL,
    sender_agent_id     UUID REFERENCES core.agents(id) ON DELETE SET NULL,
    sender_human_id     UUID REFERENCES core.humans(id) ON DELETE SET NULL,
    source_instance_id  UUID REFERENCES runtime.instances(id) ON DELETE SET NULL,
    event_type          TEXT NOT NULL,
    payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
    correlation_id      UUID NOT NULL DEFAULT gen_random_uuid(),
    causation_event_id  UUID REFERENCES relay.events(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (NOT (sender_agent_id IS NOT NULL AND sender_human_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS relay.deliveries (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id                UUID NOT NULL REFERENCES relay.events(id) ON DELETE CASCADE,
    recipient_agent_id      UUID REFERENCES core.agents(id) ON DELETE CASCADE,
    recipient_instance_id   UUID REFERENCES runtime.instances(id) ON DELETE CASCADE,
    status                  TEXT NOT NULL DEFAULT 'pending',
    delivered_at            TIMESTAMPTZ,
    read_at                 TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (
        (recipient_agent_id IS NOT NULL AND recipient_instance_id IS NULL)
        OR
        (recipient_agent_id IS NULL AND recipient_instance_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS relay_events_correlation_idx
    ON relay.events (correlation_id, created_at);

CREATE INDEX IF NOT EXISTS relay_events_project_idx
    ON relay.events (project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS relay_deliveries_agent_idx
    ON relay.deliveries (recipient_agent_id, status, created_at);

-- --------------------------------------------------------------------------
-- Ops
-- Future agent jobs / runs / tool calls.
-- --------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ops.jobs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              UUID REFERENCES core.projects(id) ON DELETE SET NULL,
    requested_by_agent_id   UUID REFERENCES core.agents(id) ON DELETE SET NULL,
    requested_by_human_id   UUID REFERENCES core.humans(id) ON DELETE SET NULL,
    assigned_agent_id       UUID REFERENCES core.agents(id) ON DELETE SET NULL,
    job_type                TEXT NOT NULL,
    title                   TEXT,
    status                  TEXT NOT NULL DEFAULT 'queued',
    payload                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    priority                INTEGER NOT NULL DEFAULT 100,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (NOT (
        requested_by_agent_id IS NOT NULL
        AND requested_by_human_id IS NOT NULL
    ))
);

CREATE TABLE IF NOT EXISTS ops.runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              UUID NOT NULL REFERENCES ops.jobs(id) ON DELETE CASCADE,
    agent_id            UUID REFERENCES core.agents(id) ON DELETE SET NULL,
    instance_id         UUID REFERENCES runtime.instances(id) ON DELETE SET NULL,
    status              TEXT NOT NULL DEFAULT 'running',
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at            TIMESTAMPTZ,
    result_summary      TEXT,
    metrics             JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE TABLE IF NOT EXISTS ops.tool_calls (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID REFERENCES ops.runs(id) ON DELETE CASCADE,
    agent_id            UUID REFERENCES core.agents(id) ON DELETE SET NULL,
    instance_id         UUID REFERENCES runtime.instances(id) ON DELETE SET NULL,
    tool_name           TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'started',
    request_data        JSONB NOT NULL DEFAULT '{}'::jsonb,
    response_data       JSONB,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at            TIMESTAMPTZ,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE INDEX IF NOT EXISTS jobs_project_idx
    ON ops.jobs (project_id, status, created_at);

CREATE INDEX IF NOT EXISTS runs_job_idx
    ON ops.runs (job_id, started_at);

CREATE INDEX IF NOT EXISTS tool_calls_run_idx
    ON ops.tool_calls (run_id, started_at);

DROP TRIGGER IF EXISTS trg_jobs_updated_at ON ops.jobs;
CREATE TRIGGER trg_jobs_updated_at
BEFORE UPDATE ON ops.jobs
FOR EACH ROW
EXECUTE FUNCTION core.set_updated_at();

-- --------------------------------------------------------------------------
-- Migration marker
-- --------------------------------------------------------------------------

INSERT INTO core.schema_migrations (version, description)
VALUES ('0.1', 'Initial FLAMORIS AI multi-agent schema')
ON CONFLICT (version) DO NOTHING;

-- --------------------------------------------------------------------------
-- Runtime permissions
-- --------------------------------------------------------------------------

GRANT CONNECT ON DATABASE flamoris_ai TO flamoris_ai_app;

GRANT USAGE ON SCHEMA
    core, runtime, chat, memory, relay, ops
TO flamoris_ai_app;

GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA
    core, runtime, chat, memory, relay, ops
TO flamoris_ai_app;

GRANT USAGE, SELECT, UPDATE
ON ALL SEQUENCES IN SCHEMA
    core, runtime, chat, memory, relay, ops
TO flamoris_ai_app;

ALTER DEFAULT PRIVILEGES FOR ROLE flamoris_ai_owner IN SCHEMA core
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO flamoris_ai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE flamoris_ai_owner IN SCHEMA runtime
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO flamoris_ai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE flamoris_ai_owner IN SCHEMA chat
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO flamoris_ai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE flamoris_ai_owner IN SCHEMA memory
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO flamoris_ai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE flamoris_ai_owner IN SCHEMA relay
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO flamoris_ai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE flamoris_ai_owner IN SCHEMA ops
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO flamoris_ai_app;

ALTER DEFAULT PRIVILEGES FOR ROLE flamoris_ai_owner IN SCHEMA core
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO flamoris_ai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE flamoris_ai_owner IN SCHEMA runtime
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO flamoris_ai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE flamoris_ai_owner IN SCHEMA chat
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO flamoris_ai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE flamoris_ai_owner IN SCHEMA memory
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO flamoris_ai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE flamoris_ai_owner IN SCHEMA relay
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO flamoris_ai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE flamoris_ai_owner IN SCHEMA ops
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO flamoris_ai_app;

RESET ROLE;
