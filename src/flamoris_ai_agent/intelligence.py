"""Temporary llama.cpp adapter. No redirects, proxies, retries or durable state."""

import asyncio
import json
from urllib.parse import urlsplit

import httpx

from flamoris_ai_agent.execution import (
    MAX_OUTPUT_BYTES,
    ExecutionRequest,
    ExecutionResult,
    IntelligenceError,
    ModelIdentity,
    validate_messages,
)

MAX_RESPONSE_BYTES = 1048576


class IntelligenceClient:
    def __init__(
        self, base_url: str, model: str | None = None, timeout: float = 120, *, transport=None
    ):
        url = urlsplit(base_url)
        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("invalid_provider_configuration")
        if not 0 < timeout <= 300:
            raise ValueError("invalid_timeout")
        self.base_url = base_url.rstrip("/")
        self.configured_model = model or None
        self.timeout = timeout
        self.http = httpx.AsyncClient(
            trust_env=False,
            follow_redirects=False,
            transport=transport,
            timeout=httpx.Timeout(timeout, connect=min(timeout, 5)),
        )

    async def aclose(self):
        await self.http.aclose()

    async def _request(self, method: str, path: str, **kwargs):
        try:
            async with asyncio.timeout(10 if method == "GET" else self.timeout):
                async with self.http.stream(method, self.base_url + path, **kwargs) as response:
                    if response.status_code != 200:
                        raise IntelligenceError("provider_unavailable")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise IntelligenceError("response_too_large")
                        body.extend(chunk)
                    return json.loads(body)
        except (TimeoutError, httpx.TimeoutException):
            raise IntelligenceError("timeout") from None
        except httpx.HTTPError:
            raise IntelligenceError("provider_unavailable") from None
        except (ValueError, UnicodeError):
            raise IntelligenceError("invalid_response") from None

    async def resolve(self) -> ModelIdentity:
        payload = await self._request("GET", "/v1/models")
        try:
            models = [item["id"] for item in payload["data"]]
            if not 1 <= len(models) <= 128 or any(
                not isinstance(m, str) or not m or len(m.encode()) > 512 for m in models
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise IntelligenceError("invalid_response") from None
        if self.configured_model:
            if self.configured_model not in models:
                raise IntelligenceError("model_absent")
            model = self.configured_model
        elif len(models) != 1:
            raise IntelligenceError("ambiguous_model")
        else:
            model = models[0]
        return ModelIdentity("llama.cpp", model)

    async def resolve_model(self) -> str:
        return (await self.resolve()).model

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        validate_messages(request.messages)
        if request.identity.provider != "llama.cpp":
            raise IntelligenceError("model_mismatch")
        payload = await self._request(
            "POST",
            "/v1/chat/completions",
            json={
                "model": request.identity.model,
                "messages": request.messages,
                "stream": False,
                "max_tokens": 4096,
            },
        )
        try:
            message = payload["choices"][0]["message"]
            text = message["content"]
            if message.get("role") != "assistant" or not isinstance(text, str) or not text.strip():
                raise ValueError
            if "model" in payload and payload["model"] != request.identity.model:
                raise IntelligenceError("model_mismatch")
            if len(text.encode("utf-8")) > MAX_OUTPUT_BYTES:
                raise IntelligenceError("output_too_large")
        except (KeyError, IndexError, TypeError, ValueError):
            raise IntelligenceError("invalid_response") from None
        return ExecutionResult(request.identity, text)
