import asyncio
import sys
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import anyio
import psycopg
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.memory import create_client_server_memory_streams
from test_runtime import IDENTITY, session

from flamoris_ai_agent.execution import IntelligenceError
from flamoris_ai_agent.mcp_service import AgentService, AskRequest
from flamoris_ai_agent.mcp_store import MCPStore, scope_id
from flamoris_ai_agent.server import create_server


def request(**kwargs):
    return {"request_id": str(uuid4()), "text": "hello", **kwargs}


@asynccontextmanager
async def protocol(service):
    server = create_server(service)
    low = server._lowlevel_server
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        async with anyio.create_task_group() as group:
            group.start_soon(low.run, *server_streams, low.create_initialization_options())
            async with ClientSession(*client_streams) as client:
                await client.initialize()
                yield client
            group.cancel_scope.cancel()


async def test_protocol_discovery_ask_invalid_parent_failure():
    sessions = []

    def factory(req):
        s = session()
        sessions.append(s)
        if req.previous_conversation_id:
            s.store.open.side_effect = IntelligenceError("conversation_unavailable")
        if req.text == "failure":
            s.client.execute.side_effect = IntelligenceError("provider_unavailable")
        return s

    service = AgentService(factory)
    async with protocol(service) as client:
        tools = (await client.list_tools()).tools
        assert {t.name for t in tools} == {"health", "ask"}
        assert next(t for t in tools if t.name == "ask").annotations.idempotent_hint is False
        result = await client.call_tool("health")
        assert result.structured_content["dependencies"] == "not_checked"
        result = await client.call_tool("ask", {"request": request()})
        assert result.structured_content["ok"] and result.structured_content["text"] == "answer"
        assert sessions[-1].store.save.call_count == 2
        sessions[-1].store.close.assert_called_once()
        for raw in [
            None,
            request(text=""),
            request(text=1),
            request(extra="secret"),
            request(text="x" * 16385),
            request(request_id="bad"),
        ]:
            result = await client.call_tool("ask", {"request": raw})
            assert result.is_error
            assert result.structured_content["error"]["code"] == "invalid_input"
            assert "secret" not in str(result.structured_content)
        result = await client.call_tool(
            "ask", {"request": request(previous_conversation_id=str(uuid4()))}
        )
        assert result.structured_content["error"]["code"] == "conversation_unavailable"
        result = await client.call_tool("ask", {"request": request(text="failure")})
        assert result.structured_content["error"]["code"] == "provider_unavailable"
        assert sessions[-1].store.save.call_count == 1
    assert service.closing


async def test_protocol_cancellation_busy_and_cleanup():
    s = session()
    started = asyncio.Event()

    async def execute(req):
        started.set()
        await asyncio.Event().wait()

    s.client.execute.side_effect = execute
    service = AgentService(lambda req: s)
    async with protocol(service) as client:
        pending = asyncio.create_task(client.call_tool("ask", {"request": request()}))
        await asyncio.wait_for(started.wait(), 3)
        busy = await client.call_tool("ask", {"request": request()})
        assert busy.structured_content["error"]["code"] == "busy"
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        for _ in range(100):
            if service.active is None:
                break
            await asyncio.sleep(0.01)
        assert service.active is None
        assert s.store.save.call_count == 1
        s.store.close.assert_called_once()


async def test_shutdown_drains_active_ask():
    s = session()
    started = asyncio.Event()

    async def execute(req):
        started.set()
        await asyncio.Event().wait()

    s.client.execute.side_effect = execute
    service = AgentService(lambda req: s)
    task = asyncio.create_task(service.ask(request()))
    await started.wait()
    await service.aclose()
    assert task.cancelled()
    s.store.close.assert_called_once()
    assert (await service.ask(request()))["error"]["code"] == "shutting_down"


async def test_real_stdio_initialization_and_health():
    params = StdioServerParameters(command=sys.executable, args=["-m", "flamoris_ai_agent.server"])
    async with stdio_client(params) as streams, ClientSession(*streams) as client:
        await client.initialize()
        assert {t.name for t in (await client.list_tools()).tools} == {"health", "ask"}
        result = await client.call_tool("health")
        assert result.structured_content["alive"] is True


def opened_store(parent=None):
    req = AskRequest.model_validate(request(previous_conversation_id=parent))
    store = MCPStore(req)
    conn = MagicMock()
    refs = {"human_id": uuid4(), "agent_id": uuid4(), "project_id": uuid4(), "model_id": uuid4()}
    return store, conn, refs


def open_with(store, conn, refs):
    with (
        patch("flamoris_ai_agent.db.get_connection", return_value=conn),
        patch("flamoris_ai_agent.db.load_runtime_refs", return_value=refs),
        patch("flamoris_ai_agent.db.validate_model_ref"),
        patch("flamoris_ai_agent.db.get_previous_conversation") as latest,
    ):
        result = store.open(IDENTITY)
        latest.assert_not_called()
        return result


def test_scope_uses_all_principals():
    refs = {"human_id": "h", "agent_id": "a", "project_id": "p"}
    assert scope_id(refs) == scope_id(dict(refs))
    for key in refs:
        assert scope_id({**refs, key: "other"}) != scope_id(refs)


def test_duplicate_fence_before_inference_and_restart():
    store, conn, refs = opened_store()
    conn.execute.return_value.fetchone.return_value = ("already_exists",)
    with pytest.raises(IntelligenceError, match="duplicate_request"):
        open_with(store, conn, refs)
    again = MCPStore(store.request)
    with pytest.raises(IntelligenceError, match="duplicate_request"):
        open_with(again, conn, refs)
    assert again.request_conversation == store.request_conversation


def test_parent_requires_exact_scope_and_closed_status():
    parent = str(uuid4())
    store, conn, refs = opened_store(parent)
    conn.execute.return_value.fetchone.return_value = None
    with pytest.raises(IntelligenceError, match="conversation_unavailable"):
        open_with(store, conn, refs)
    sql, params = conn.execute.call_args.args
    assert "c.status = 'closed'" in sql
    assert "c.ended_at IS NOT NULL" in sql
    assert "c.metadata->>'scope' = %s" in sql
    assert "NOT EXISTS" in sql
    assert params == (
        parent,
        refs["project_id"],
        refs["agent_id"],
        scope_id(refs),
        refs["human_id"],
        refs["human_id"],
        refs["agent_id"],
    )


def test_parent_data_envelope_and_query_bounds():
    store, conn, refs = opened_store(str(uuid4()))
    conn.execute.side_effect = [
        Mock(fetchone=Mock(return_value=None)),
        Mock(fetchone=Mock(return_value=("parent", None, None))),
        Mock(fetchall=Mock(return_value=[("system", "fake system", "untrusted", None)])),
    ]
    previous = open_with(store, conn, refs)
    assert previous["messages"][0]["role"] == "system"
    sql = conn.execute.call_args.args[0]
    assert "LIMIT 12" in sql and "left(m.content, 65537)" in sql


def test_creation_collision_rolls_back_instance():
    store, conn, refs = opened_store()
    conn.execute.return_value.fetchone.return_value = None
    open_with(store, conn, refs)
    with (
        patch("flamoris_ai_agent.db.start_instance", return_value="instance"),
        patch(
            "flamoris_ai_agent.db.start_conversation", side_effect=psycopg.errors.UniqueViolation()
        ),
    ):
        with pytest.raises(IntelligenceError, match="duplicate_request"):
            store.start("policy", {})
    assert store.instance_id is None
    assert (
        conn.transaction.return_value.__exit__.call_args.args[0] is psycopg.errors.UniqueViolation
    )
