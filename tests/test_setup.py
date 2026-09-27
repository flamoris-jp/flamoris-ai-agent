from contextlib import nullcontext

from flamoris_ai_agent.setup import setup_identity


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self):
        self.calls = []
        self.next_id = 1

    def transaction(self):
        return nullcontext()

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "RETURNING id" in sql:
            value = self.next_id
            self.next_id += 1
            return Result((value,))
        return Result()


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


def test_setup_identity_is_safe_to_rerun(monkeypatch):
    configured_env(monkeypatch)
    conn = FakeConnection()

    setup_identity(conn)
    setup_identity(conn)

    assert len(conn.calls) == 10
