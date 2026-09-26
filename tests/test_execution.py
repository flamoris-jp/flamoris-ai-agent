import asyncio
import json

import httpx
import pytest

from flamoris_ai_agent.execution import ExecutionRequest, IntelligenceError, ModelIdentity
from flamoris_ai_agent.intelligence import IntelligenceClient

IDENTITY = ModelIdentity("llama.cpp", "served")
MESSAGES = [{"role": "system", "content": "identity"}, {"role": "user", "content": "hello"}]


def run_handler(handler, action):
    async def run():
        client = IntelligenceClient("http://provider", transport=httpx.MockTransport(handler))
        try:
            return await action(client)
        finally:
            await client.aclose()

    return asyncio.run(run())


def test_resolution_payload_and_identity():
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "served"}]})
        return httpx.Response(
            200,
            json={
                "model": "served",
                "choices": [{"message": {"role": "assistant", "content": "こんにちは"}}],
            },
        )

    async def action(client):
        identity = await client.resolve()
        return await client.execute(ExecutionRequest(identity, MESSAGES))

    result = run_handler(handler, action)
    assert result.identity == IDENTITY
    assert result.text == "こんにちは"
    assert json.loads(requests[-1].content) == {
        "model": "served",
        "messages": MESSAGES,
        "stream": False,
        "max_tokens": 4096,
    }


@pytest.mark.parametrize(
    "body,code",
    [
        ({"data": []}, "invalid_response"),
        ({"data": [{"id": "a"}, {"id": "b"}]}, "ambiguous_model"),
        ({"data": [{"id": 12}]}, "invalid_response"),
    ],
)
def test_model_rejection(body, code):
    with pytest.raises(IntelligenceError, match=code):
        run_handler(lambda r: httpx.Response(200, json=body), lambda c: c.resolve())


@pytest.mark.parametrize(
    "response,code",
    [
        (
            httpx.Response(302, headers={"location": "https://private-secret"}),
            "provider_unavailable",
        ),
        (httpx.Response(500, text="secret prompt"), "provider_unavailable"),
        (httpx.Response(200, content=b"x" * 1048577), "response_too_large"),
        (httpx.Response(200, text="not JSON"), "invalid_response"),
        (httpx.Response(200, json={"choices": []}), "invalid_response"),
        (
            httpx.Response(
                200, json={"choices": [{"message": {"role": "assistant", "content": "x" * 65537}}]}
            ),
            "output_too_large",
        ),
    ],
)
def test_bounded_fixed_errors(response, code):
    calls = []

    def handler(request):
        calls.append(request)
        return response

    with pytest.raises(IntelligenceError) as error:
        run_handler(handler, lambda c: c.execute(ExecutionRequest(IDENTITY, MESSAGES)))
    assert str(error.value) == code
    assert len(calls) == 1


def test_input_rejected_before_io():
    def handler(request):
        pytest.fail("network should not be used")

    with pytest.raises(IntelligenceError, match="input_too_large"):
        run_handler(
            handler,
            lambda c: c.execute(
                ExecutionRequest(
                    IDENTITY,
                    [{"role": "user", "content": "x" * 65537}],
                )
            ),
        )


def test_timeout_and_cancellation():
    async def run():
        started = asyncio.Event()

        async def handler(request):
            started.set()
            await asyncio.Event().wait()

        client = IntelligenceClient(
            "http://provider", timeout=0.02, transport=httpx.MockTransport(handler)
        )
        try:
            with pytest.raises(IntelligenceError, match="timeout"):
                await client.execute(ExecutionRequest(IDENTITY, MESSAGES))
            client.timeout = 120
            started.clear()
            task = asyncio.create_task(client.execute(ExecutionRequest(IDENTITY, MESSAGES)))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            await client.aclose()

    asyncio.run(run())


def test_network_error_does_not_expose_url():
    def handler(request):
        raise httpx.ConnectError("http://private:secret@host", request=request)

    with pytest.raises(IntelligenceError) as error:
        run_handler(handler, lambda c: c.resolve())
    assert str(error.value) == "provider_unavailable"
