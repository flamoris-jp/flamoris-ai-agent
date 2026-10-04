from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import httpx2
from test_http import TOKEN
from test_mcp import request
from test_runtime import session
from test_scoped_service import Principals

from flamoris_ai_agent.delegation import authenticated_delegator
from flamoris_ai_agent.http_server import HTTPSettings, create_http_app
from flamoris_ai_agent.scoped_service import ScopedAgentService


@asynccontextmanager
async def internal(service):
    app = create_http_app(HTTPSettings(TOKEN, delegator_key="backend"), service)
    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="http://localhost:8768",
            headers={"Authorization": f"Bearer {TOKEN}"},
        ) as client:
            yield client


async def test_internal_scoped_http_preserves_principals_request_identity_and_revocation():
    principals = Principals()
    captured = []

    def factory(req, bound):
        instance = session()
        captured.append((req, bound, instance))
        return instance

    service = ScopedAgentService(principals, factory, AsyncMock())
    async with internal(service) as client:
        caps = (await client.get("/api/v1/capabilities")).json()
        assert caps["api_version"] == 1
        assert set(caps["operations"]) == {
            "health",
            "sessions.open",
            "ask_scoped",
            "ask_availability",
        }
        assert (await client.post("/api/v1/ask", json=request())).status_code == 404
        handles = []
        for human in ("first", "second"):
            opened = (
                await client.post(
                    "/api/v1/sessions/open",
                    json={
                        "human": human,
                        "agent": "helper",
                        "project": "project",
                    },
                )
            ).json()
            assert opened["ok"]
            handles.append(opened["session_id"])
            raw = request(session_id=opened["session_id"], text=human)
            answer = (await client.post("/api/v1/ask-scoped", json=raw)).json()
            assert answer["ok"] and answer["text"] == "answer"
            assert answer["session_id"] == opened["session_id"]
            assert answer["request_id"] == raw["request_id"]
            assert len(captured) == len(handles)
            assert authenticated_delegator.get() is None
        denied = (
            await client.post(
                "/api/v1/ask-scoped",
                json=request(
                    session_id=handles[0],
                    human="second",
                ),
            )
        ).json()
        assert denied["error"]["code"] == "invalid_input"
        principals.disabled = True
        denied = (
            await client.post("/api/v1/ask-scoped", json=request(session_id=handles[0]))
        ).json()
        assert denied["error"]["code"] == "principal_unavailable"
    assert [bound.keys.human for _, bound, _ in captured] == ["first", "second"]
    assert captured[0][2] is not captured[1][2]
    for _, _, instance in captured:
        instance.store.close.assert_called_once()


async def test_internal_settings_catalog_is_opt_in_and_uses_domain_grants(monkeypatch):
    monkeypatch.setenv("AGENT_SETTINGS_ENABLED", "1")
    service = ScopedAgentService(Principals())
    async with internal(service) as client:
        caps = (await client.get("/api/v1/capabilities")).json()
        assert {
            "models.allowed",
            "personality.get",
            "personality.history",
            "personality.save",
        } <= set(caps["operations"])
        response = await client.post(
            "/api/v1/personality/save", json={"session_id": "private-invalid"}
        )
        assert response.json()["error"]["code"] == "invalid_input"
        assert "private-invalid" not in response.text
