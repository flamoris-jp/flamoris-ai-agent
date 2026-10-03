import json
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_intelligence_mcp import TARGET
from test_scoped_service import Principals, shared_http

from flamoris_ai_agent.delegation import authenticated_delegator
from flamoris_ai_agent.execution import IntelligenceError
from flamoris_ai_agent.model_settings import ModelSettings, registry
from flamoris_ai_agent.personality import ContextSnapshot, PersonalityBody
from flamoris_ai_agent.runtime import configured_session
from flamoris_ai_agent.scoped_service import ScopedAgentService


def option(provider="llamacpp"):
    remote = provider == "openai"
    target = {
        **TARGET.model_dump(),
        "public_model_id": "api" if remote else "local",
        "provider_id": provider,
        "db_model_name": "snapshot" if remote else "served-alias",
        "db_provider": "openai" if remote else "llama.cpp",
        "data_flow": "remote_authorized" if remote else "local_only",
    }
    return {
        "id": target["public_model_id"],
        "display_name": "API" if remote else "Internal",
        "model_key": "registered-api" if remote else "registered-local",
        "target": target,
    }


def test_registry_bounded_exact_identity_and_no_caller_urls(monkeypatch):
    for values in [
        [option(), option()],
        [{**option(), "id": "different"}],
        [{**option(), "endpoint": "https://caller.invalid"}],
        [],
    ]:
        monkeypatch.setenv("AGENT_INTELLIGENCE_TARGETS", json.dumps(values))
        with pytest.raises(IntelligenceError, match="invalid_intelligence_configuration"):
            registry()
    monkeypatch.setenv("AGENT_INTELLIGENCE_TARGETS", json.dumps([option(), option("openai")]))
    assert set(registry()) == {"local", "api"}
    first = registry()["api"].digest
    monkeypatch.setenv("AGENT_INTELLIGENCE_MCP_ENDPOINT", "http://127.0.0.1:9999/mcp")
    assert registry()["api"].digest != first


@pytest.mark.parametrize(
    "sections",
    [
        [{"title": "Same", "content": "a"}, {"title": "Same", "content": "b"}],
        [{"title": "\x00", "content": "b"}],
        [{"title": "A", "content": "🦉" * 9000}],
        [{"title": "A", "content": "\x00"}],
        [],
    ],
)
def test_personality_bounds_and_unique_titles(sections):
    with pytest.raises((ValidationError, UnicodeError)):
        PersonalityBody(display_name="Helper", sections=sections)


def test_console_cannot_use_remote_target_without_granted_session(monkeypatch):
    monkeypatch.setenv("AGENT_INTELLIGENCE_TRANSPORT", "mcp")
    monkeypatch.setenv("AGENT_INTELLIGENCE_TARGET", json.dumps(option("openai")["target"]))
    with pytest.raises(IntelligenceError, match="remote_export_forbidden"):
        configured_session()


def test_continuation_restores_snapshot_without_loading_current_files():
    from flamoris_ai_agent.mcp_store import MCPStore

    store = object.__new__(MCPStore)
    store.previous_snapshot = {
        "agent_sections": [{"title": "Old", "content": "old"}],
        "personality_revision": 3,
    }
    loader = Mock(side_effect=RuntimeError("new source is unavailable"))
    context = store.restore_context(loader)
    assert context == [{"title": "Old", "content": "old"}] and context.revision == 3
    loader.assert_not_called()
    store.previous_snapshot = None
    loader.side_effect = None
    loader.return_value = ContextSnapshot([{"title": "New", "content": "new"}], 4)
    assert store.restore_context(loader).revision == 4


async def test_settings_catalog_is_opt_in_and_read_permission_errors_are_sanitized(monkeypatch):
    monkeypatch.setenv("AGENT_SETTINGS_ENABLED", "1")
    service = ScopedAgentService(Principals())
    service.personalities = Mock()
    service.personalities.get.side_effect = IntelligenceError("personality_forbidden")
    async with shared_http(service) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        assert names == {
            "health",
            "sessions.open",
            "ask_scoped",
            "ask_availability",
            "models.allowed",
            "personality.get",
            "personality.save",
            "personality.history",
        }
        result = await client.call_tool(
            "personality.get", {"request": {"session_id": str(uuid4())}}
        )
        assert (
            result.is_error
            and result.structured_content["error"]["code"] == "personality_forbidden"
        )
    assert service.personalities.get.call_args.args[0] == "backend"


async def test_missing_caller_or_invalid_settings_does_not_touch_database(monkeypatch):
    monkeypatch.setenv("AGENT_SETTINGS_ENABLED", "1")
    service = ScopedAgentService(Principals())
    service.personalities = Mock()
    assert (await service.settings_operation("get", {"session_id": str(uuid4())}))["ok"] is False
    token = authenticated_delegator.set("backend")
    try:
        result = await service.settings_operation(
            "get", {"session_id": str(uuid4()), "human": "other"}
        )
        assert result["error"]["code"] == "invalid_input"
    finally:
        authenticated_delegator.reset(token)
    service.personalities.get.assert_not_called()


def test_remote_bind_requires_grant_and_consent_before_option_write(monkeypatch):
    monkeypatch.setenv("AGENT_INTELLIGENCE_TARGETS", json.dumps([option("openai")]))
    settings = ModelSettings(Mock())
    conn = Mock()
    bound = Mock()
    with patch.object(settings, "allowed_on", return_value=uuid4()):
        with pytest.raises(IntelligenceError, match="remote_consent_required"):
            settings.bind_on(conn, bound, "api", False)
    conn.execute.assert_not_called()
