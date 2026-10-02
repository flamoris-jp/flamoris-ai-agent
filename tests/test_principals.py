from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from test_config import create_agent
from test_mcp import request

from flamoris_ai_agent import config
from flamoris_ai_agent.execution import IntelligenceError
from flamoris_ai_agent.mcp_service import AskRequest
from flamoris_ai_agent.mcp_store import MCPStore
from flamoris_ai_agent.principals import PrincipalBinding, PrincipalKeys, PrincipalSessions


@pytest.mark.parametrize("value", ["", "../person", "person.name", "x" * 65, 1, None])
def test_principal_keys_are_bounded_and_closed(value):
    with pytest.raises(IntelligenceError, match="principal_unavailable"):
        PrincipalKeys(value, "helper", "project")


def test_explicit_agent_context_does_not_mutate_process_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AGENT_HOME", tmp_path)
    monkeypatch.setenv("FLAMORIS_AGENT_KEY", "first")
    create_agent(tmp_path, "first", files={"identity.md": "First identity"})
    create_agent(tmp_path, "second", files={"identity.md": "Second identity"})
    assert config.load_agent_context("second")[0]["content"] == "Second identity"
    assert config.load_agent_context()[0]["content"] == "First identity"
    with pytest.raises(config.AgentContextError):
        config.load_agent_context("missing")


def binding():
    return PrincipalBinding(
        uuid4(),
        "backend",
        PrincipalKeys("person", "helper", "project"),
        uuid4(),
        uuid4(),
        uuid4(),
        datetime.now(UTC),
    )


def test_binding_is_immutable_and_missing_transport_grant_fails_before_connection():
    bound = binding()
    with pytest.raises(FrozenInstanceError):
        bound.keys = PrincipalKeys("other", "helper", "project")
    connections = MagicMock()
    with pytest.raises(IntelligenceError, match="principal_unavailable"):
        PrincipalSessions(connections).open(None, bound.keys)
    connections.assert_not_called()


def test_scoped_store_rechecks_binding_before_creating_any_runtime_state():
    bound = binding()
    principals = MagicMock()
    principals.require_on.side_effect = IntelligenceError("principal_unavailable")
    store = MCPStore(AskRequest.model_validate(request()), binding=bound, principals=principals)
    store.conn = MagicMock()
    store.refs = bound.ids
    store.scope = "scope"
    store.request_conversation = uuid4()
    with pytest.raises(IntelligenceError, match="principal_unavailable"):
        store.start("policy", {})
    store.conn.execute.assert_not_called()
    assert store.instance_id is None


def test_no_silent_scoped_store_fallback():
    with pytest.raises(IntelligenceError, match="principal_unavailable"):
        MCPStore(AskRequest.model_validate(request()), binding=binding())
