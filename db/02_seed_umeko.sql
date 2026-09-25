-- ============================================================================
-- FLAMORIS AI v0.1 seed: Akino + Umeko + local host
-- Run while connected to flamoris_ai as PostgreSQL superuser.
-- ============================================================================

SET ROLE flamoris_ai_owner;

-- Root project
INSERT INTO core.projects (
    project_key, slug, name, project_type, description
)
VALUES (
    'flamoris', 'flamoris', 'FLAMORIS', 'root',
    'FLAMORIS全体のルートプロジェクト'
)
ON CONFLICT (project_key) DO UPDATE
SET name = EXCLUDED.name,
    description = EXCLUDED.description;

-- AI area
INSERT INTO core.projects (
    parent_project_id, project_key, slug, name, project_type, description
)
SELECT
    p.id,
    'flamoris.ai',
    'ai',
    'AI',
    'area',
    'FLAMORIS AI / Agent 基盤'
FROM core.projects AS p
WHERE p.project_key = 'flamoris'
ON CONFLICT (project_key) DO UPDATE
SET parent_project_id = EXCLUDED.parent_project_id,
    name = EXCLUDED.name,
    description = EXCLUDED.description;

-- Umeko project
INSERT INTO core.projects (
    parent_project_id, project_key, slug, name, project_type, description
)
SELECT
    p.id,
    'flamoris.ai.umeko',
    'umeko',
    '梅子',
    'agent_project',
    'ローカルAI 梅子'
FROM core.projects AS p
WHERE p.project_key = 'flamoris.ai'
ON CONFLICT (project_key) DO UPDATE
SET parent_project_id = EXCLUDED.parent_project_id,
    name = EXCLUDED.name,
    description = EXCLUDED.description;

-- Human: Akino
INSERT INTO core.humans (
    human_key, display_name
)
VALUES (
    'akino', '愛乃'
)
ON CONFLICT (human_key) DO UPDATE
SET display_name = EXCLUDED.display_name;

-- Agent: Umeko
INSERT INTO core.agents (
    agent_key, display_name, agent_type, default_project_id,
    metadata
)
SELECT
    'umeko',
    '梅子',
    'character_agent',
    p.id,
    '{"story_role":"Bass"}'::jsonb
FROM core.projects AS p
WHERE p.project_key = 'flamoris.ai.umeko'
ON CONFLICT (agent_key) DO UPDATE
SET display_name = EXCLUDED.display_name,
    agent_type = EXCLUDED.agent_type,
    default_project_id = EXCLUDED.default_project_id,
    metadata = EXCLUDED.metadata;

-- Umeko belongs to her project
INSERT INTO core.agent_projects (
    agent_id, project_id, project_role, inherit_parent
)
SELECT
    a.id,
    p.id,
    'member',
    TRUE
FROM core.agents AS a
JOIN core.projects AS p
  ON p.project_key = 'flamoris.ai.umeko'
WHERE a.agent_key = 'umeko'
ON CONFLICT (agent_id, project_id) DO UPDATE
SET project_role = EXCLUDED.project_role,
    inherit_parent = EXCLUDED.inherit_parent;

-- Host: local machine
INSERT INTO runtime.hosts (
    host_key, hostname, display_name, host_type, os_name
)
VALUES (
    'local-host', 'localhost', 'Local Host', 'machine', 'Windows'
)
ON CONFLICT (host_key) DO UPDATE
SET hostname = EXCLUDED.hostname,
    display_name = EXCLUDED.display_name,
    host_type = EXCLUDED.host_type,
    os_name = EXCLUDED.os_name;

-- Application: Umeko console chat
INSERT INTO runtime.applications (
    application_key, name, app_type, version
)
VALUES (
    'umeko-chat', 'Umeko Chat', 'agent_chat', '0.1'
)
ON CONFLICT (application_key) DO UPDATE
SET name = EXCLUDED.name,
    app_type = EXCLUDED.app_type,
    version = EXCLUDED.version;

-- Model identity: Agent and model are deliberately separate.
INSERT INTO runtime.models (
    model_key, provider, model_name, base_model_name, context_window
)
VALUES (
    'ollama:umeko',
    'ollama',
    'umeko',
    'qwen2.5:7b',
    4096
)
ON CONFLICT (model_key) DO UPDATE
SET provider = EXCLUDED.provider,
    model_name = EXCLUDED.model_name,
    base_model_name = EXCLUDED.base_model_name,
    context_window = EXCLUDED.context_window;

RESET ROLE;
