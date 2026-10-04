"""Narrow Agent execution adapter over the reusable non-MCP provider library."""

import json
import os

from flamoris_intelligence import create_service
from flamoris_intelligence.config import ModelEntry, Settings
from flamoris_intelligence.contracts import IntelligenceError as ProviderError

from flamoris_ai_agent.execution import (
    MAX_OUTPUT_BYTES,
    ExecutionResult,
    IntelligenceError,
    ModelIdentity,
    validate_messages,
)
from flamoris_ai_agent.execution_target import ApprovedTarget

ERROR_CODES = {
    "provider_timeout": "timeout",
    "invalid_provider_response": "invalid_response",
    "response_limit": "response_too_large",
    "invalid_request": "invalid_input",
    "unknown_model": "model_mismatch",
}


def provider_error(exc):
    return IntelligenceError(ERROR_CODES.get(exc.code, exc.code))


def provider_settings(target):
    # All network/credential policy is operator-owned. Callers choose only an
    # already-granted ID; persona text and request JSON cannot supply endpoints.
    try:
        return Settings.from_env(
            provider_url=os.getenv("INTELLIGENCE_BASE_URL", "http://127.0.0.1:8081"),
            models=(
                ModelEntry(
                    id=target.public_model_id,
                    provider_id=target.provider_id,
                    provider_model=target.db_model_name,
                    context_tokens=target.context_tokens,
                    max_output_tokens=target.max_output_tokens,
                ),
            ),
            timeout_seconds=target.timeout_seconds,
            health_timeout_seconds=10,
            max_input_bytes=target.max_input_bytes,
            max_response_bytes=1048576,
            max_output_bytes=MAX_OUTPUT_BYTES,
            max_concurrency=1,
        )
    except (ValueError, TypeError):
        raise IntelligenceError("invalid_intelligence_configuration") from None


class ApprovedExecutionClient:
    def __init__(self, target: ApprovedTarget, *, transport=None):
        self.target = target
        self.identity = ModelIdentity(target.db_provider, target.db_model_name)
        self.service = create_service(provider_settings(target), transport=transport)
        self.resolved = False
        self.closed = False

    async def resolve(self):
        if self.closed:
            raise IntelligenceError("invalid_lifecycle")
        try:
            descriptor = await self.service.model_available(self.target.public_model_id)
            if (
                descriptor.get("available") is not True
                or descriptor.get("provider_id") != self.target.provider_id
                or descriptor.get("model_id") != self.target.public_model_id
            ):
                raise IntelligenceError("model_mismatch")
            self.resolved = True
            return self.identity
        except ProviderError as exc:
            raise provider_error(exc) from None

    def _request(self, request):
        if self.closed:
            raise IntelligenceError("invalid_lifecycle")
        validate_messages(request.messages)
        if not self.resolved or request.identity != self.identity:
            raise IntelligenceError("model_mismatch")
        if request.messages[0]["role"] != "system" or any(
            message["role"] == "system" for message in request.messages[1:]
        ):
            raise IntelligenceError("invalid_input")
        if (
            sum(len(message["content"].encode()) for message in request.messages)
            > self.target.max_input_bytes
        ):
            raise IntelligenceError("input_too_large")
        raw = {
            "model_id": self.target.public_model_id,
            "capability_id": self.target.capability_id,
            "messages": request.messages,
            "max_output_tokens": self.target.max_output_tokens,
            "timeout_seconds": self.target.timeout_seconds,
        }
        if len(json.dumps(raw, ensure_ascii=True).encode()) > 131072:
            raise IntelligenceError("input_too_large")
        try:
            self.service.validate_messages(raw)
        except ProviderError as exc:
            raise provider_error(exc) from None
        return raw

    async def validate(self, request):
        self._request(request)

    async def execute(self, request):
        try:
            data = await self.service.execute_messages(self._request(request))
        except ProviderError as exc:
            raise provider_error(exc) from None
        if data.get("ok") is not True:
            code = data.get("error", {}).get("code", "invalid_response")
            raise IntelligenceError(ERROR_CODES.get(code, code))
        if (
            data.get("provider_id") != self.target.provider_id
            or data.get("model_id") != self.target.public_model_id
        ):
            raise IntelligenceError("model_mismatch")
        if data.get("finish_reason") == "length":
            raise IntelligenceError("incomplete_output")
        text = data.get("text")
        if data.get("finish_reason") != "stop" or type(text) is not str or not text.strip():
            raise IntelligenceError("invalid_response")
        if len(text.encode()) > MAX_OUTPUT_BYTES:
            raise IntelligenceError("output_too_large")
        return ExecutionResult(
            self.identity,
            text,
            ModelIdentity(self.target.provider_id, self.target.public_model_id),
            data.get("execution_id"),
            data.get("usage"),
        )

    async def aclose(self):
        self.closed = True
        await self.service.close()
