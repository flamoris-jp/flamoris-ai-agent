import asyncio
import json
from contextlib import asynccontextmanager
from unittest.mock import Mock
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import ValidationError

from flamoris_ai_agent.direct_execution import ApprovedExecutionClient
from flamoris_ai_agent.execution import ExecutionRequest, IntelligenceError, ModelIdentity
from flamoris_ai_agent.execution_target import ApprovedTarget
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
    {"role": "assistant", "content": "previous answer"},
    {"role": "user", "content": "new question"},
]


class Upstream:
    def __init__(self):
        self.calls = []
        self.models = {"data": [{"id": "served-alias"}]}
        self.result = {
            "model": "served-alias",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "answer"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        }
        self.started = asyncio.Event()
        self.wait = False
        self.status = 200

    async def handle(self, request):
        if request.method == "GET":
            self.calls.append((request.url.path, None))
            return httpx.Response(200, json=self.models)
        self.calls.append((request.url.path, json.loads(request.content)))
        self.started.set()
        if self.wait:
            await asyncio.Event().wait()
        return httpx.Response(self.status, json=self.result)


@asynccontextmanager
async def connected(upstream, target=TARGET):
    client = ApprovedExecutionClient(target, transport=httpx.MockTransport(upstream.handle))
    try:
        yield client
    finally:
        await client.aclose()


async def test_direct_provider_preserves_roles_and_public_to_db_identity():
    upstream = Upstream()
    async with connected(upstream) as client:
        assert await client.resolve() == IDENTITY
        result = await client.execute(ExecutionRequest(IDENTITY, MESSAGES))
        assert result.identity == IDENTITY and result.text == "answer"
        assert result.public_identity == ModelIdentity("llamacpp", "public-model")
        assert str(UUID(result.execution_id)) == result.execution_id
        assert result.usage == {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}
    assert [name for name, _ in upstream.calls] == ["/v1/models", "/v1/chat/completions"]
    payload = upstream.calls[-1][1]
    assert payload["model"] == "served-alias" and payload["messages"] == MESSAGES
    assert "tools" not in payload and payload["stream"] is False


@pytest.mark.parametrize(
    "models",
    [
        {"data": [{"id": "other"}]},
        {"data": []},
        {"data": [{"id": True}]},
    ],
)
async def test_exact_model_probe_denies_before_conversation(models):
    upstream = Upstream()
    upstream.models = models
    store = Mock()
    async with connected(upstream) as client:
        agent = AgentSession(client, store, context_loader=lambda: [])
        with pytest.raises(IntelligenceError):
            await agent.start()
        store.open.assert_not_called()
        store.start.assert_not_called()
    assert upstream.calls == [("/v1/models", None)]


@pytest.mark.parametrize(
    "change,code",
    [
        ("partial", "incomplete_output"),
        ("empty", "invalid_response"),
        ("model", "invalid_response"),
        ("usage_sum", "invalid_response"),
        ("usage_budget", "invalid_response"),
        ("output", "response_too_large"),
    ],
)
async def test_invalid_or_partial_result_keeps_user_turn_without_success(change, code):
    upstream = Upstream()
    choice = upstream.result["choices"][0]
    if change == "partial":
        choice["finish_reason"] = "length"
    elif change == "empty":
        choice["message"]["content"] = ""
    elif change == "model":
        upstream.result["model"] = "other"
    elif change == "usage_sum":
        upstream.result["usage"]["total_tokens"] = 13
    elif change == "usage_budget":
        upstream.result["usage"] = {
            "prompt_tokens": 1,
            "completion_tokens": 1025,
            "total_tokens": 1026,
        }
    else:
        choice["message"]["content"] = "x" * 65537
    store = Mock()
    store.open.return_value = None
    store.start.return_value = (uuid4(), uuid4())
    async with connected(upstream) as client:
        agent = AgentSession(client, store, context_loader=lambda: [])
        await agent.start()
        with pytest.raises(IntelligenceError, match=code):
            await agent.ask("question")
        assert [call.args[0] for call in store.save.call_args_list] == ["user"]
        assert len([name for name, _ in upstream.calls if name == "/v1/chat/completions"]) == 1
        await agent.aclose()


async def test_combined_limits_reject_before_user_save_and_provider_dispatch():
    upstream = Upstream()
    store = Mock()
    store.open.return_value = None
    store.start.return_value = (uuid4(), uuid4())
    async with connected(upstream, TARGET.model_copy(update={"max_input_bytes": 2000})) as client:
        agent = AgentSession(client, store, context_loader=lambda: [])
        await agent.start()
        with pytest.raises(IntelligenceError, match="input_too_large"):
            await agent.ask("x" * 2000)
        store.save.assert_not_called()
        assert upstream.calls == [("/v1/models", None)]
    async with connected(Upstream(), TARGET.model_copy(update={"context_tokens": 2048})) as client:
        await client.resolve()
        with pytest.raises(IntelligenceError, match="context_limit"):
            await client.execute(
                ExecutionRequest(
                    IDENTITY,
                    [
                        {"role": "system", "content": "x" * 800},
                        {"role": "user", "content": "y"},
                    ],
                )
            )


async def test_serialized_request_limit_includes_unicode_escaping():
    upstream = Upstream()
    async with connected(upstream, TARGET.model_copy(update={"context_tokens": 100000})) as client:
        await client.resolve()
        with pytest.raises(IntelligenceError, match="input_too_large"):
            await client.validate(
                ExecutionRequest(
                    IDENTITY,
                    [
                        {"role": "system", "content": "p"},
                        {"role": "user", "content": "😸" * 13000},
                    ],
                )
            )


async def test_cancellation_drains_without_replaying_inference():
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
    assert len([name for name, _ in upstream.calls if name == "/v1/chat/completions"]) == 1


def test_retired_modes_and_remote_default_never_fall_back(monkeypatch):
    with pytest.raises(ValidationError):
        ApprovedTarget.model_validate({**TARGET.model_dump(), "data_flow": "remote_allowed"})
    for mode in ("mcp", "typo"):
        monkeypatch.setenv("AGENT_INTELLIGENCE_TRANSPORT", mode)
        with pytest.raises(IntelligenceError, match="invalid_intelligence_configuration"):
            configured_session()
    monkeypatch.setenv("AGENT_INTELLIGENCE_TRANSPORT", "direct")
    monkeypatch.setenv("AGENT_INTELLIGENCE_MCP_ENDPOINT", "http://localhost:8767/mcp")
    with pytest.raises(IntelligenceError, match="invalid_intelligence_configuration"):
        configured_session()


async def test_only_public_provenance_reaches_agent_response():
    upstream = Upstream()
    store = Mock()
    store.open.return_value = None
    store.start.return_value = (uuid4(), uuid4())
    async with connected(upstream) as client:
        service = AgentService(lambda _: AgentSession(client, store, context_loader=lambda: []))
        answer = await service.ask({"request_id": str(uuid4()), "text": "question"})
    assert answer["ok"] and answer["provenance"]["provider"] == "llamacpp"
    assert answer["provenance"]["model"] == "public-model"
    assert str(UUID(answer["provenance"]["execution_id"])) == answer["provenance"]["execution_id"]
    assert "served-alias" not in json.dumps(answer)
    assert store.save.call_args.args[2]["intelligence_model"] == "served-alias"
    assert store.save.call_args.args[2]["intelligence_usage"]["total_tokens"] == 12


async def test_private_provider_failure_is_sanitized_and_not_retried():
    upstream = Upstream()
    upstream.status = 500
    upstream.result = {"error": "private-body"}
    async with connected(upstream) as client:
        await client.resolve()
        with pytest.raises(IntelligenceError, match="^provider_unavailable$"):
            await client.execute(ExecutionRequest(IDENTITY, MESSAGES))
    assert len(upstream.calls) == 2
