-- FLAMORIS AI v0.1 smoke test

SELECT version();

SELECT
    version,
    description,
    applied_at
FROM core.schema_migrations
ORDER BY applied_at;

SELECT
    project_key,
    name,
    depth,
    slug_path_text,
    name_path_text
FROM core.project_paths
ORDER BY slug_path_text;

SELECT
    a.agent_key,
    a.display_name AS agent,
    p.project_key,
    p.name AS default_project
FROM core.agents AS a
LEFT JOIN core.projects AS p
  ON p.id = a.default_project_id
ORDER BY a.agent_key;

SELECT
    h.host_key,
    h.display_name,
    h.host_type,
    h.os_name
FROM runtime.hosts AS h
ORDER BY h.host_key;

SELECT
    application_key,
    name,
    version
FROM runtime.applications
ORDER BY application_key;

SELECT
    model_key,
    provider,
    model_name,
    base_model_name,
    context_window
FROM runtime.models
ORDER BY model_key;
