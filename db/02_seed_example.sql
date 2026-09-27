-- ============================================================================
-- FLAMORIS AI example seed
-- Synthetic public sample data only.
--
-- Production deployments should use flamoris-agent-setup with private .env values.
-- Run this only for local examples/tests while connected to flamoris_ai as a
-- PostgreSQL superuser.
-- ============================================================================

SET ROLE flamoris_ai_owner;

INSERT INTO core.projects (
    project_key, slug, name, project_type, description
)
VALUES (
    'example.project',
    'example-project',
    'Example Project',
    'agent_project',
    'Synthetic public example project'
)
ON CONFLICT (project_key) DO UPDATE
SET slug = EXCLUDED.slug,
    name = EXCLUDED.name,
    description = EXCLUDED.description;

INSERT INTO core.humans (
    human_key, display_name
)
VALUES (
    'example-user',
    'Example User'
)
ON CONFLICT (human_key) DO UPDATE
SET display_name = EXCLUDED.display_name;

INSERT INTO core.agents (
    agent_key, display_name, agent_type, default_project_id
)
SELECT
    'example-agent',
    'Example Agent',
    'agent',
    p.id
FROM core.projects AS p
WHERE p.project_key = 'example.project'
ON CONFLICT (agent_key) DO UPDATE
SET display_name = EXCLUDED.display_name,
    agent_type = EXCLUDED.agent_type,
    default_project_id = EXCLUDED.default_project_id;

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
  ON p.project_key = 'example.project'
WHERE a.agent_key = 'example-agent'
ON CONFLICT (agent_id, project_id) DO UPDATE
SET project_role = EXCLUDED.project_role,
    inherit_parent = EXCLUDED.inherit_parent;

INSERT INTO runtime.applications (
    application_key, name, app_type, version
)
VALUES (
    'flamoris-ai-agent',
    'FLAMORIS AI Agent',
    'agent_runtime',
    '0.1'
)
ON CONFLICT (application_key) DO UPDATE
SET name = EXCLUDED.name,
    app_type = EXCLUDED.app_type,
    version = EXCLUDED.version;

RESET ROLE;
