"""Agent-owned schema/history validation; no DB initialization or replay."""

from flamoris_update_core.domain import check_resources, configuration_revision
from flamoris_update_core.errors import UpdateError
from flamoris_update_core.owner import ApplicationOwner, DomainState
from flamoris_update_core.owner_cli import serve

SCHEMAS = {"configuration": "agent-config-1", "database": "005_model_continuations"}
MIGRATIONS = {
    "0.1",
    "002_principal_sessions",
    "003_principal_retention",
    "004_assistant_settings",
    "005_model_continuations",
}


def inspect_domain(config, resources):
    check_resources(resources, ["configuration"], ["database"])
    database = resources["database"]
    if set(database.binding.schemas) != {"core", "runtime", "chat", "memory", "relay", "ops"}:
        raise UpdateError("invalid_profile")
    with database.connect() as conn, conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        actual = {
            row[0] for row in conn.execute("SELECT version FROM core.schema_migrations").fetchall()
        }
        if actual != MIGRATIONS:
            raise UpdateError("unsupported_migration")
        # An unfinished MCP conversation is durable uncertain work. No process
        # restart or missing PID makes a provider request safe to replay.
        uncertain = bool(
            conn.execute(
                "SELECT 1 FROM chat.conversations WHERE metadata->>'client'='agent-mcp' "
                "AND ended_at IS NULL LIMIT 1"
            ).fetchone()
        )
    return DomainState(
        schemas=SCHEMAS,
        active_work=uncertain,
        unknown_work=uncertain,
        configuration_digest=configuration_revision(resources),
    )


def factory(config):
    return ApplicationOwner(config, "flamoris-ai-agent", "1.0.2", inspect_domain)


def main():
    serve(factory)
