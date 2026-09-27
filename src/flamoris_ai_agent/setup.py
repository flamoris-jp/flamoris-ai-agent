"""Initialize the configured single-principal Agent deployment from environment values."""

import asyncio
import os

from flamoris_ai_agent.db import _required_env, get_connection
from flamoris_ai_agent.register_runtime import register_configured_runtime


def _optional_env(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    if not value:
        raise RuntimeError(f"{name} must not be empty")
    return value


def setup_identity(conn) -> None:
    human_key = _required_env("FLAMORIS_HUMAN_KEY")
    human_name = _required_env("FLAMORIS_HUMAN_DISPLAY_NAME")
    agent_key = _required_env("FLAMORIS_AGENT_KEY")
    agent_name = _required_env("FLAMORIS_AGENT_DISPLAY_NAME")
    project_key = _required_env("FLAMORIS_PROJECT_KEY")
    project_name = _required_env("FLAMORIS_PROJECT_NAME")
    project_slug = _required_env("FLAMORIS_PROJECT_SLUG")
    application_key = _required_env("FLAMORIS_APPLICATION_KEY")
    application_name = _required_env("FLAMORIS_APPLICATION_NAME")
    agent_type = _optional_env("FLAMORIS_AGENT_TYPE", "agent")

    with conn.transaction():
        project_id = conn.execute(
            """
            INSERT INTO core.projects (
                project_key, slug, name, project_type, description
            )
            VALUES (%s, %s, %s, 'agent_project', 'Configured Agent project')
            ON CONFLICT (project_key) DO UPDATE
            SET slug = EXCLUDED.slug,
                name = EXCLUDED.name
            RETURNING id
            """,
            (project_key, project_slug, project_name),
        ).fetchone()[0]

        conn.execute(
            """
            INSERT INTO core.humans (human_key, display_name)
            VALUES (%s, %s)
            ON CONFLICT (human_key) DO UPDATE
            SET display_name = EXCLUDED.display_name
            RETURNING id
            """,
            (human_key, human_name),
        ).fetchone()[0]

        agent_id = conn.execute(
            """
            INSERT INTO core.agents (
                agent_key, display_name, agent_type, default_project_id
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (agent_key) DO UPDATE
            SET display_name = EXCLUDED.display_name,
                agent_type = EXCLUDED.agent_type,
                default_project_id = EXCLUDED.default_project_id
            RETURNING id
            """,
            (agent_key, agent_name, agent_type, project_id),
        ).fetchone()[0]

        conn.execute(
            """
            INSERT INTO core.agent_projects (
                agent_id, project_id, project_role, inherit_parent
            )
            VALUES (%s, %s, 'member', TRUE)
            ON CONFLICT (agent_id, project_id) DO UPDATE
            SET project_role = EXCLUDED.project_role,
                inherit_parent = EXCLUDED.inherit_parent
            """,
            (agent_id, project_id),
        )

        conn.execute(
            """
            INSERT INTO runtime.applications (
                application_key, name, app_type, version
            )
            VALUES (%s, %s, 'agent_runtime', '0.1')
            ON CONFLICT (application_key) DO UPDATE
            SET name = EXCLUDED.name,
                app_type = EXCLUDED.app_type,
                version = EXCLUDED.version
            """,
            (application_key, application_name),
        )

    print(
        "Configured identity: "
        f"human={human_key}, agent={agent_key}, project={project_key}, "
        f"application={application_key}"
    )


async def setup_configured_deployment() -> None:
    with get_connection() as conn:
        setup_identity(conn)
    await register_configured_runtime()


def main() -> None:
    asyncio.run(setup_configured_deployment())


if __name__ == "__main__":
    main()
