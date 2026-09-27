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


def _require_match(label: str, key: str, actual, expected) -> None:
    if actual != expected:
        raise RuntimeError(f"{label} key {key!r} already exists with different identity metadata")


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
        project = conn.execute(
            """
            SELECT id, slug, name, project_type
            FROM core.projects
            WHERE project_key = %s
            """,
            (project_key,),
        ).fetchone()
        if project is None:
            project_id = conn.execute(
                """
                INSERT INTO core.projects (
                    project_key, slug, name, project_type, description
                )
                VALUES (%s, %s, %s, 'agent_project', 'Configured Agent project')
                RETURNING id
                """,
                (project_key, project_slug, project_name),
            ).fetchone()[0]
        else:
            project_id = project[0]
            _require_match(
                "Project",
                project_key,
                project[1:],
                (project_slug, project_name, "agent_project"),
            )

        human = conn.execute(
            """
            SELECT id, display_name
            FROM core.humans
            WHERE human_key = %s
            """,
            (human_key,),
        ).fetchone()
        if human is None:
            conn.execute(
                """
                INSERT INTO core.humans (human_key, display_name)
                VALUES (%s, %s)
                """,
                (human_key, human_name),
            )
        else:
            _require_match("Human", human_key, human[1], human_name)

        agent = conn.execute(
            """
            SELECT id, display_name, agent_type, default_project_id
            FROM core.agents
            WHERE agent_key = %s
            """,
            (agent_key,),
        ).fetchone()
        if agent is None:
            agent_id = conn.execute(
                """
                INSERT INTO core.agents (
                    agent_key, display_name, agent_type, default_project_id
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (agent_key, agent_name, agent_type, project_id),
            ).fetchone()[0]
        else:
            agent_id = agent[0]
            _require_match(
                "Agent",
                agent_key,
                agent[1:],
                (agent_name, agent_type, project_id),
            )

        membership = conn.execute(
            """
            SELECT project_role, inherit_parent
            FROM core.agent_projects
            WHERE agent_id = %s AND project_id = %s
            """,
            (agent_id, project_id),
        ).fetchone()
        if membership is None:
            conn.execute(
                """
                INSERT INTO core.agent_projects (
                    agent_id, project_id, project_role, inherit_parent
                )
                VALUES (%s, %s, 'member', TRUE)
                """,
                (agent_id, project_id),
            )
        else:
            _require_match(
                "Agent project membership",
                f"{agent_key}:{project_key}",
                membership,
                ("member", True),
            )

        application = conn.execute(
            """
            SELECT name, app_type, version
            FROM runtime.applications
            WHERE application_key = %s
            """,
            (application_key,),
        ).fetchone()
        if application is None:
            conn.execute(
                """
                INSERT INTO runtime.applications (
                    application_key, name, app_type, version
                )
                VALUES (%s, %s, 'agent_runtime', '0.1')
                """,
                (application_key, application_name),
            )
        else:
            _require_match(
                "Application",
                application_key,
                application,
                (application_name, "agent_runtime", "0.1"),
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
