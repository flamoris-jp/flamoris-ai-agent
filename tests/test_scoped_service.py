import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import httpx2
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from test_http import TOKEN
from test_mcp import request
from test_runtime import session

from flamoris_ai_agent.delegation import authenticated_delegator
from flamoris_ai_agent.execution import IntelligenceError
from flamoris_ai_agent.http_server import HTTPSettings, create_http_app
from flamoris_ai_agent.mcp_service import AgentService
from flamoris_ai_agent.principals import PrincipalBinding, PrincipalKeys
from flamoris_ai_agent.scoped_service import ScopedAgentService


class Principals:
    def __init__(self):
        self.bindings = {}
        self.disabled = False

    def open(self, caller, keys):
        if (
            caller != "backend"
            or keys.human not in ("first", "second")
            or (keys.agent, keys.project) != ("helper", "project")
        ):
            raise IntelligenceError("principal_unavailable")
        binding = PrincipalBinding(
            uuid4(),
            caller,
            keys,
            uuid4(),
            uuid4(),
            uuid4(),
            datetime.now(UTC) + timedelta(minutes=15),
        )
        self.bindings[str(binding.session_id)] = binding
        return binding

    def require(self, caller, session_id):
        bound = self.bindings.get(str(session_id))
        if self.disabled or bound is None or bound.delegator != caller:
            raise IntelligenceError("principal_unavailable")
        return bound


@asynccontextmanager
async def shared_http(service):
    app = create_http_app(HTTPSettings(TOKEN, delegator_key="backend"), service)
    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="http://localhost:8768",
            headers={"Authorization": f"Bearer {TOKEN}"},
        ) as transport:
            async with streamable_http_client(
                "http://localhost:8768/mcp", http_client=transport
            ) as streams:
                async with ClientSession(streams[0], streams[1]) as client:
                    await client.initialize()
                    yield client


async def test_http_binding_two_principals_preserves_separate_sessions_and_catalog():
    principals = Principals()
    captured = []

    def factory(req, bound):
        instance = session()
        captured.append((req, bound, instance))
        return instance

    service = ScopedAgentService(principals, factory)
    async with shared_http(service) as client:
        tools = (await client.list_tools()).tools
        assert {t.name for t in tools} == {"health", "sessions.open", "ask_scoped"}
        for name in ("first", "second"):
            result = await client.call_tool(
                "sessions.open",
                {"request": {"human": name, "agent": "helper", "project": "project"}},
            )
            assert result.structured_content["ok"]
            handle = result.structured_content["session_id"]
            result = await client.call_tool(
                "ask_scoped", {"request": request(session_id=handle, text=name)}
            )
            assert result.structured_content["text"] == "answer"
            assert result.structured_content["session_id"] == handle
            assert authenticated_delegator.get() is None
    assert [bound.keys.human for _, bound, _ in captured] == ["first", "second"]
    assert [req.text for req, _, _ in captured] == ["first", "second"]
    assert captured[0][2] is not captured[1][2]
    for _, _, instance in captured:
        instance.store.close.assert_called_once()


async def test_missing_transport_identity_cannot_open_or_ask_or_fall_back():
    principals = Mock()
    factory = Mock()
    service = ScopedAgentService(principals, factory)
    assert (
        await service.open_session({"human": "first", "agent": "helper", "project": "project"})
    )["error"]["code"] == "principal_unavailable"
    assert (await service.ask_scoped(request(session_id=str(uuid4()))))["error"][
        "code"
    ] == "principal_unavailable"
    assert (await service.ask(request()))["error"]["code"] == "principal_required"
    principals.open.assert_not_called()
    principals.require.assert_not_called()
    factory.assert_not_called()


async def test_forbidden_malformed_or_revoked_principal_has_no_inference():
    principals = Principals()
    factory = Mock(side_effect=AssertionError("must not create AgentSession"))
    service = ScopedAgentService(principals, factory)
    async with shared_http(service) as client:
        for raw in (
            {"human": "other", "agent": "helper", "project": "project"},
            {"human": "first", "agent": "helper", "project": "project", "delegator": "backend"},
        ):
            result = await client.call_tool("sessions.open", {"request": raw})
            assert result.is_error
        opened = await client.call_tool(
            "sessions.open",
            {"request": {"human": "first", "agent": "helper", "project": "project"}},
        )
        handle = opened.structured_content["session_id"]
        for raw in (
            request(session_id=handle, human="second"),
            request(session_id="invalid"),
            request(session_id=handle, text=""),
        ):
            result = await client.call_tool("ask_scoped", {"request": raw})
            assert result.is_error and result.structured_content["error"]["code"] == "invalid_input"
        principals.disabled = True
        result = await client.call_tool("ask_scoped", {"request": request(session_id=handle)})
        assert (
            result.is_error
            and result.structured_content["error"]["code"] == "principal_unavailable"
        )
    factory.assert_not_called()


async def test_competing_scoped_requests_keep_global_admission_and_cleanup():
    principals = Principals()
    first = principals.open("backend", PrincipalKeys("first", "helper", "project"))
    second = principals.open("backend", PrincipalKeys("second", "helper", "project"))
    started = asyncio.Event()
    instance = session()

    async def execute(req):
        started.set()
        await asyncio.Event().wait()

    instance.client.execute.side_effect = execute
    captured = []

    def factory(req, bound):
        captured.append(bound)
        return instance

    service = ScopedAgentService(principals, factory)
    caller = authenticated_delegator.set("backend")
    try:
        pending = asyncio.create_task(service.ask_scoped(request(session_id=str(first.session_id))))
        await asyncio.wait_for(started.wait(), 3)
        result = await service.ask_scoped(request(session_id=str(second.session_id)))
        assert result == {"ok": False, "error": {"code": "busy"}}
        assert captured == [first]
        await service.aclose()
        assert pending.cancelled() and service.active is None
        instance.store.close.assert_called_once()
    finally:
        authenticated_delegator.reset(caller)


def test_shared_http_is_explicit_and_cannot_be_mixed_with_fixed_service():
    with pytest.raises(ValueError, match="invalid_principal_transport"):
        create_http_app(HTTPSettings(TOKEN), ScopedAgentService(Principals()))
    with pytest.raises(ValueError, match="invalid_principal_transport"):
        create_http_app(HTTPSettings(TOKEN, delegator_key="backend"), AgentService())
    with pytest.raises(ValueError, match="invalid_http_delegator"):
        HTTPSettings(TOKEN, delegator_key="../backend")


async def test_another_authenticated_delegator_cannot_reuse_a_binding():
    principals = Principals()
    bound = principals.open("backend", PrincipalKeys("first", "helper", "project"))
    service = ScopedAgentService(principals, Mock())
    caller = authenticated_delegator.set("other-backend")
    try:
        result = await service.ask_scoped(request(session_id=str(bound.session_id)))
        assert result["error"]["code"] == "principal_unavailable"
        service.scoped_session_factory.assert_not_called()
    finally:
        authenticated_delegator.reset(caller)
