from contextlib import nullcontext

import pytest

from flamoris_ai_agent.setup import setup_identity


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self):
        self.calls = []
        self.project = None
        self.human = None
        self.agent = None
        self.membership = None
        self.application = None

    def transaction(self):
        return nullcontext()

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        normalized = " ".join(sql.split())

        if normalized.startswith("SELECT id, slug, name, project_type FROM core.projects"):
            return Result(self.project)
        if normalized.startswith("INSERT INTO core.projects"):
            self.project = (1, params[1], params[2], "agent_project")
            return Result((1,))

        if normalized.startswith("SELECT id, display_name FROM core.humans"):
            return Result(self.human)
        if normalized.startswith("INSERT INTO core.humans"):
            self.human = (2, params[1])
            return Result()

        if normalized.startswith(
            "SELECT id, display_name, agent_type, default_project_id FROM core.agents"
        ):
            return Result(self.agent)
        if normalized.startswith("INSERT INTO core.agents"):
            self.agent = (3, params[1], params[2], params[3])
            return Result((3,))

        if normalized.startswith(
            "SELECT project_role, inherit_parent FROM core.agent_projects"
        ):
            return Result(self.membership)
        if normalized.startswith("INSERT INTO core.agent_projects"):
            self.membership = ("member", True)
            return Result()

        if normalized.startswith("SELECT name, app_type, version FROM runtime.applications"):
            return Result(self.application)
        if normalized.startswith("INSERT INTO runtime.applications"):
            self.application = (params[1], "agent_runtime", "0.1")
            return Result()

        raise AssertionError(f"Unexpected SQL: {normalized}")


def configured_env(monkeypatch):
    values = {
        "FLAMORIS_HUMAN_KEY": "example-user",
        "FLAMORIS_HUMAN_DISPLAY_NAME": "Example User",
        "FLAMORIS_AGENT_KEY": "example-agent",
        "FLAMORIS_AGENT_DISPLAY_NAME": "Example Agent",
        "FLAMORIS_PROJECT_KEY": "example.project",
        "FLAMORIS_PROJECT_NAME": "Example Project",
        "FLAMORIS_PROJECT_SLUG": "example-project",
        "FLAMORIS_APPLICATION_KEY": "flamoris-ai-agent",
        "FLAMORIS_APPLICATION_NAME": "FLAMORIS AI Agent",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_setup_identity_uses_environment_values(monkeypatch):
    configured_env(monkeypatch)
    conn = FakeConnection()

    setup_identity(conn)

    flattened = repr(conn.calls)
    assert "example-user" in flattened
    assert "Example Agent" in flattened
    assert "example.project" in flattened
    assert "flamoris-ai-agent" in flattened


def test_setup_identity_is_idempotent(monkeypatch):
    configured_env(monkeypatch)
    conn = FakeConnection()

    setup_identity(conn)
    first_call_count = len(conn.calls)
    setup_identity(conn)

    second_run = conn.calls[first_call_count:]
    assert all("INSERT INTO" not in sql for sql, _ in second_run)


def test_setup_identity_rejects_conflicting_agent_metadata(monkeypatch):
    configured_env(monkeypatch)
    conn = FakeConnection()
    conn.project = (1, "example-project", "Example Project", "agent_project")
    conn.human = (2, "Example User")
    conn.agent = (3, "Different Agent", "agent", 1)

    with pytest.raises(RuntimeError, match="different identity metadata"):
        setup_identity(conn)
