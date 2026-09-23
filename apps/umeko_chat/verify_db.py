from db import get_connection, load_runtime_refs


def main():
    with get_connection() as conn:
        refs = load_runtime_refs(conn)

        version = conn.execute(
            "SELECT version FROM core.schema_migrations ORDER BY applied_at DESC LIMIT 1"
        ).fetchone()

        project = conn.execute(
            """
            SELECT project_key, name, name_path_text
            FROM core.project_paths
            WHERE id = %s
            """,
            (refs["project_id"],),
        ).fetchone()

        agent = conn.execute(
            "SELECT agent_key, display_name FROM core.agents WHERE id = %s",
            (refs["agent_id"],),
        ).fetchone()

        host = conn.execute(
            "SELECT host_key, display_name FROM runtime.hosts WHERE id = %s",
            (refs["host_id"],),
        ).fetchone()

        app = conn.execute(
            """
            SELECT application_key, name
            FROM runtime.applications
            WHERE id = %s
            """,
            (refs["application_id"],),
        ).fetchone()

        model = conn.execute(
            """
            SELECT model_key, provider, model_name, base_model_name
            FROM runtime.models
            WHERE id = %s
            """,
            (refs["model_id"],),
        ).fetchone()

    print("FLAMORIS AI DB接続 OK")
    print(f"schema version : {version[0] if version else 'unknown'}")
    print(f"project        : {project[0]} / {project[2]}")
    print(f"agent          : {agent[0]} / {agent[1]}")
    print(f"host           : {host[0]} / {host[1]}")
    print(f"application    : {app[0]} / {app[1]}")
    print(f"model          : {model[0]} / {model[1]}:{model[2]} ({model[3]})")


if __name__ == "__main__":
    main()
