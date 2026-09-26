from contextlib import asynccontextmanager
from unittest.mock import Mock

import httpx2
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from test_mcp import request
from test_runtime import session

from flamoris_ai_agent.http_server import HTTPSettings, create_http_app
from flamoris_ai_agent.mcp_service import AgentService

TOKEN = "test-only-credential-never-for-production"


@asynccontextmanager
async def http(service=None):
    app = create_http_app(HTTPSettings(TOKEN), service)
    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="http://localhost:8768",
            headers={"Authorization": f"Bearer {TOKEN}"},
        ) as client:
            yield client


async def test_http_protocol_multiple_asks_and_cleanup():
    sessions = []

    def factory(req):
        s = session()
        sessions.append(s)
        return s

    service = AgentService(factory)
    async with http(service) as transport:
        async with streamable_http_client(
            "http://localhost:8768/mcp", http_client=transport
        ) as streams:
            async with ClientSession(streams[0], streams[1]) as client:
                await client.initialize()
                assert {t.name for t in (await client.list_tools()).tools} == {"health", "ask"}
                for _ in range(2):
                    result = await client.call_tool("ask", {"request": request()})
                    assert result.structured_content["text"] == "answer"
                    assert not service.closing
                result = await client.call_tool("ask", {"request": request(text="")})
                assert result.structured_content["error"]["code"] == "invalid_input"
    assert service.closing
    assert len(sessions) == 2
    for s in sessions:
        s.store.close.assert_called_once()


@pytest.mark.parametrize(
    ("headers", "status"),
    [
        ({"Authorization": ""}, 401),
        ({"Authorization": "Bearer secret-invalid"}, 401),
        ([("Authorization", f"Bearer {TOKEN}"), ("Authorization", f"Bearer {TOKEN}")], 401),
        ({"Host": "attacker.invalid"}, 421),
        ({"Origin": "http://localhost:8768"}, 403),
        ({"Content-Encoding": "gzip"}, 415),
    ],
)
async def test_http_rejects_before_dispatch(headers, status):
    factory = Mock(side_effect=AssertionError("must not reach runtime"))
    async with http(AgentService(factory)) as client:
        result = await client.post("/mcp", headers=headers, content=b"private-prompt")
        assert result.status_code == status
        assert "secret" not in result.text and "private-prompt" not in result.text
    factory.assert_not_called()


async def test_http_body_limit_and_liveness_without_dependencies():
    factory = Mock(side_effect=AssertionError("must not reach runtime"))
    async with http(AgentService(factory)) as client:
        response = await client.get("/healthz", headers={"Authorization": ""})
        assert response.json() == {"alive": True}
        response = await client.post(
            "/mcp",
            content=b"x" * 131073,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        assert response.status_code == 413
    factory.assert_not_called()


@pytest.mark.parametrize("token", ["", "short", "x" * 513, "x" * 32 + " ", "猫" * 32])
def test_http_settings_fail_closed(token):
    with pytest.raises(ValueError, match="invalid_http_credential"):
        HTTPSettings(token)
    assert TOKEN not in repr(HTTPSettings(TOKEN))


def test_http_settings_environment(monkeypatch):
    monkeypatch.delenv("AGENT_MCP_TOKEN", raising=False)
    with pytest.raises(ValueError, match="invalid_http_configuration"):
        HTTPSettings.from_env()
    monkeypatch.setenv("AGENT_MCP_TOKEN", TOKEN)
    monkeypatch.setenv("AGENT_HTTP_ALLOWED_HOSTS", "*")
    with pytest.raises(ValueError, match="invalid_http_configuration"):
        HTTPSettings.from_env()
