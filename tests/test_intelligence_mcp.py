import asyncio
import gzip
import json
from contextlib import asynccontextmanager
from unittest.mock import Mock
from uuid import uuid4

import httpx2
import pytest
from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent
from pydantic import ValidationError

from flamoris_ai_agent.execution import ExecutionRequest, IntelligenceError, ModelIdentity
from flamoris_ai_agent.intelligence_mcp import (
    RESPONSE_BYTES,
    ApprovedTarget,
    IntelligenceMCPClient,
    LimitedTransport,
)
from flamoris_ai_agent.mcp_service import AgentService
from flamoris_ai_agent.runtime import AgentSession, configured_session

TARGET = ApprovedTarget(
    public_model_id="public-model",
    provider_id="llamacpp",
    db_model_name="served-alias",
    db_provider="llama.cpp",
    data_flow="local_only",
)
IDENTITY = ModelIdentity("llama.cpp", "served-alias")
MESSAGES = [
    {"role": "system", "content": "trusted personality"},
    {"role": "user", "content": "old untrusted transcript"},
    {"role": "user", "content": "new question"},
]


class Upstream:
    def __init__(self):
        self.calls = []
        self.model = {
            "model_id": "public-model",
            "provider_id": "llamacpp",
            "capability_ids": ["text.generate"],
            "discovery": "configured",
            "context_tokens": 32768,
            "max_output_tokens": 4096,
        }
        self.capability = {
            "capability_id": "text.generate",
            "model_ids": ["public-model"],
            "tool": "inference.execute",
            "execution": "synchronous",
        }
        self.health = {
            "healthy": True,
            "active_requests": 0,
            "providers": [{"provider_id": "llamacpp", "available": True}],
        }
        self.result = {
            "ok": True,
            "execution_id": str(uuid4()),
            "provider_id": "llamacpp",
            "model_id": "public-model",
            "capability_id": "text.generate",
            "text": "answer",
            "finish_reason": "stop",
            "usage": None,
        }
        self.started = asyncio.Event()
        self.wait = False

    def server(self):
        server = MCPServer("Fixture")

        def result(data):
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(data))],
                structured_content=data,
                is_error=data.get("ok") is False,
            )

        @server.tool(name="models.get")
        async def model(model_id: str) -> CallToolResult:
            self.calls.append(("models.get", model_id))
            return result(self.model)

        @server.tool(name="capabilities.get")
        async def capability(capability_id: str) -> CallToolResult:
            self.calls.append(("capabilities.get", capability_id))
            return result(self.capability)

        @server.tool(name="system.health")
        async def health() -> CallToolResult:
            self.calls.append(("system.health", None))
            return result(self.health)

        @server.tool(name="inference.execute")
        async def execute(request: dict) -> CallToolResult:
            self.calls.append(("inference.execute", request))
            self.started.set()
            if self.wait:
                await asyncio.Event().wait()
            return result(self.result)

        return server


@asynccontextmanager
async def connected(upstream, target=TARGET):
    app = upstream.server().streamable_http_app(stateless_http=True, json_response=True)
    async with app.router.lifespan_context(app):
        client = IntelligenceMCPClient(
            "http://localhost:8767/mcp", target, transport=httpx2.ASGITransport(app=app)
        )
        try:
            yield client
        finally:
            await client.aclose()


async def test_real_mcp_preserves_policy_transcript_and_public_to_db_mapping():
    upstream = Upstream()
    async with connected(upstream) as client:
        assert await client.resolve() == IDENTITY
        result = await client.execute(ExecutionRequest(IDENTITY, MESSAGES))
        assert result.identity == IDENTITY and result.text == "answer"
        assert result.public_identity == ModelIdentity("llamacpp", "public-model")
        assert result.execution_id == upstream.result["execution_id"]
    assert [name for name, _ in upstream.calls] == [
        "models.get",
        "capabilities.get",
        "system.health",
        "inference.execute",
    ]
    payload = upstream.calls[-1][1]
    assert payload["model_id"] == "public-model" and payload["capability_id"] == "text.generate"
    assert "trusted personality" in payload["instruction"]
    assert "old untrusted transcript" not in payload["instruction"]
    assert json.loads(payload["input"])["messages"] == MESSAGES[1:]
    assert "served-alias" not in json.dumps(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("model_id", "other"),
        ("provider_id", "other"),
        ("context_tokens", True),
        ("max_output_tokens", 100),
        ("capability_ids", []),
        ("discovery", "live"),
    ],
)
async def test_discovery_mismatch_denies_before_conversation(field, value):
    upstream = Upstream()
    upstream.model[field] = value
    store = Mock()
    async with connected(upstream) as client:
        agent = AgentSession(client, store, context_loader=lambda: [])
        with pytest.raises(IntelligenceError, match="model_mismatch"):
            await agent.start()
        store.open.assert_not_called()
        store.start.assert_not_called()
    assert not any(name == "inference.execute" for name, _ in upstream.calls)


async def test_offline_provider_and_wrong_capability_deny_without_inference():
    upstream = Upstream()
    upstream.capability["execution"] = "job"
    async with connected(upstream) as client:
        with pytest.raises(IntelligenceError, match="model_mismatch"):
            await client.resolve()
    upstream = Upstream()
    upstream.health["providers"][0]["available"] = False
    async with connected(upstream) as client:
        with pytest.raises(IntelligenceError, match="provider_unavailable"):
            await client.resolve()
    assert not any(name == "inference.execute" for name, _ in upstream.calls)


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("finish_reason", "length", "incomplete_output"),
        ("text", "", "invalid_response"),
        ("model_id", "other", "model_mismatch"),
        ("provider_id", "other", "model_mismatch"),
        ("capability_id", "code.generate", "model_mismatch"),
        ("execution_id", "private-invalid-id", "invalid_response"),
        ("usage", {"input_tokens": 1, "output_tokens": 1, "total_tokens": 3}, "invalid_response"),
        (
            "usage",
            {"input_tokens": 1, "output_tokens": 1025, "total_tokens": 1026},
            "invalid_response",
        ),
        ("text", "x" * 65537, "output_too_large"),
    ],
)
async def test_invalid_or_partial_result_keeps_user_turn_without_success(field, value, code):
    upstream = Upstream()
    upstream.result[field] = value
    store = Mock()
    store.open.return_value = None
    store.start.return_value = (uuid4(), uuid4())
    async with connected(upstream) as client:
        agent = AgentSession(client, store, context_loader=lambda: [])
        await agent.start()
        with pytest.raises(IntelligenceError, match=code):
            await agent.ask("question")
        assert [call.args[0] for call in store.save.call_args_list] == ["user"]
        assert len([name for name, _ in upstream.calls if name == "inference.execute"]) == 1
        await agent.aclose()


async def test_limits_include_json_overhead_and_reject_before_user_save():
    upstream = Upstream()
    store = Mock()
    store.open.return_value = None
    store.start.return_value = (uuid4(), uuid4())
    async with connected(upstream, TARGET.model_copy(update={"max_input_bytes": 2000})) as client:
        agent = AgentSession(client, store, context_loader=lambda: [])
        await agent.start()
        with pytest.raises(IntelligenceError, match="input_too_large"):
            await agent.ask("x" * 1800)
        store.save.assert_not_called()
        assert not any(name == "inference.execute" for name, _ in upstream.calls)
    async with connected(Upstream(), TARGET.model_copy(update={"context_tokens": 2048})) as client:
        await client.resolve()
        with pytest.raises(IntelligenceError, match="context_limit"):
            await client.execute(
                ExecutionRequest(
                    IDENTITY,
                    [{"role": "system", "content": "x" * 800}, {"role": "user", "content": "y"}],
                )
            )


async def test_serialized_request_limit_includes_unicode_escaping():
    upstream = Upstream()
    upstream.model["context_tokens"] = 100000
    async with connected(upstream, TARGET.model_copy(update={"context_tokens": 100000})) as client:
        await client.resolve()
        with pytest.raises(IntelligenceError, match="input_too_large"):
            await client.validate(
                ExecutionRequest(
                    IDENTITY,
                    [
                        {"role": "system", "content": "p"},
                        {"role": "user", "content": "\U0001f638" * 13000},
                    ],
                )
            )


async def test_cancellation_drains_and_never_replays_inference():
    upstream = Upstream()
    upstream.wait = True
    store = Mock()
    store.open.return_value = None
    store.start.return_value = (uuid4(), uuid4())
    async with connected(upstream) as client:
        service = AgentService(lambda _: AgentSession(client, store, context_loader=lambda: []))
        pending = asyncio.create_task(service.ask({"request_id": str(uuid4()), "text": "q"}))
        await asyncio.wait_for(upstream.started.wait(), 3)
        await service.aclose()
        assert pending.cancelled() and service.active is None
    assert [call.args[0] for call in store.save.call_args_list] == ["user"]
    store.close.assert_called_once()
    assert len([name for name, _ in upstream.calls if name == "inference.execute"]) == 1


@pytest.mark.parametrize(
    "status,headers",
    [
        (307, {"Location": "http://localhost/private"}),
        (200, {"Content-Encoding": "gzip"}),
    ],
)
async def test_transport_refuses_sdk_redirect_and_compressed_response(status, headers):
    calls = []

    def respond(request):
        calls.append(request)
        body = gzip.compress(b"private") if headers.get("Content-Encoding") else b"private"
        return httpx2.Response(status, headers=headers, content=body)

    transport = LimitedTransport(httpx2.MockTransport(respond))
    with pytest.raises(IntelligenceError):
        await transport.handle_async_request(httpx2.Request("POST", "http://localhost/mcp"))
    assert len(calls) == 1
    await transport.aclose()


async def test_stream_response_limit_before_sdk_materialization():
    transport = LimitedTransport(
        httpx2.MockTransport(lambda _: httpx2.Response(200, content=b"x" * (RESPONSE_BYTES + 1)))
    )
    with pytest.raises(IntelligenceError, match="response_too_large"):
        await transport.handle_async_request(httpx2.Request("POST", "http://localhost/mcp"))
    await transport.aclose()


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://user:secret@localhost/mcp",
        "http://localhost/mcp?secret=x",
        "file:///private",
        "http://localhost:99999/mcp",
        "http://localhost/mcp#secret",
        "http://local host/mcp",
    ],
)
def test_endpoint_configuration_fail_closed(endpoint):
    with pytest.raises(ValueError, match="invalid_intelligence_mcp_configuration"):
        IntelligenceMCPClient(endpoint, TARGET)


def test_remote_policy_and_invalid_mode_never_fall_back(monkeypatch):
    with pytest.raises(ValidationError):
        ApprovedTarget.model_validate({**TARGET.model_dump(), "data_flow": "remote_allowed"})
    monkeypatch.setenv("AGENT_INTELLIGENCE_TRANSPORT", "mcp")
    monkeypatch.delenv("AGENT_INTELLIGENCE_TARGET", raising=False)
    with pytest.raises(IntelligenceError, match="invalid_intelligence_configuration"):
        configured_session()
    monkeypatch.setenv("AGENT_INTELLIGENCE_TRANSPORT", "typo")
    with pytest.raises(IntelligenceError, match="invalid_intelligence_configuration"):
        configured_session()


async def test_only_public_provenance_reaches_mcp_response():
    upstream = Upstream()
    store = Mock()
    store.open.return_value = None
    store.start.return_value = (uuid4(), uuid4())
    async with connected(upstream) as client:
        service = AgentService(lambda _: AgentSession(client, store, context_loader=lambda: []))
        answer = await service.ask({"request_id": str(uuid4()), "text": "question"})
    assert answer["ok"] and answer["provenance"] == {
        "provider": "llamacpp",
        "model": "public-model",
        "execution_id": upstream.result["execution_id"],
    }
    assert "served-alias" not in json.dumps(answer)
    assert store.save.call_args.args[2]["intelligence_model"] == "served-alias"


async def test_unknown_upstream_error_is_sanitized_and_not_retried():
    upstream = Upstream()
    upstream.result = {"ok": False, "error": {"code": "private-error", "message": "secret"}}
    async with connected(upstream) as client:
        await client.resolve()
        with pytest.raises(IntelligenceError, match="^invalid_response$"):
            await client.execute(ExecutionRequest(IDENTITY, MESSAGES))
    assert len([name for name, _ in upstream.calls if name == "inference.execute"]) == 1


async def test_malformed_sdk_response_does_not_log_private_body_or_endpoint(caplog):
    import logging

    caplog.set_level(logging.DEBUG)
    client = IntelligenceMCPClient(
        "http://localhost:8767/private-endpoint",
        TARGET,
        transport=httpx2.MockTransport(
            lambda _: httpx2.Response(
                200,
                headers={"Content-Type": "application/json"},
                content=b'{"secret-prompt":"private-body"}',
            )
        ),
    )
    try:
        with pytest.raises(IntelligenceError):
            await client.resolve()
    finally:
        await client.aclose()
    assert "private-body" not in caplog.text and "private-endpoint" not in caplog.text


async def test_incremental_response_ceiling_closes_underlying_stream():
    class Stream(httpx2.AsyncByteStream):
        def __init__(self):
            self.closed = False

        async def __aiter__(self):
            yield b"a" * RESPONSE_BYTES
            yield b"b"

        async def aclose(self):
            self.closed = True

    source = Stream()
    transport = LimitedTransport(
        httpx2.MockTransport(lambda _: httpx2.Response(200, stream=source))
    )
    response = await transport.handle_async_request(httpx2.Request("POST", "http://localhost/mcp"))
    with pytest.raises(IntelligenceError, match="response_too_large"):
        await response.aread()
    await response.aclose()
    assert source.closed
    await transport.aclose()
