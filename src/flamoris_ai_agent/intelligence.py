"""Legacy console configuration over the reusable direct llama.cpp adapter."""

from flamoris_intelligence.config import Settings
from flamoris_intelligence.contracts import IntelligenceError as ProviderError
from flamoris_intelligence.contracts import MessageInferenceRequest
from flamoris_intelligence.llamacpp import LlamaCppProvider

from flamoris_ai_agent.direct_execution import provider_error
from flamoris_ai_agent.execution import (
    MAX_OUTPUT_BYTES,
    ExecutionRequest,
    ExecutionResult,
    IntelligenceError,
    ModelIdentity,
    validate_messages,
)


class IntelligenceClient:
    def __init__(
        self, base_url: str, model: str | None = None, timeout: float = 120, *, transport=None
    ):
        if not 0 < timeout <= 120:
            raise ValueError("invalid_timeout")
        self.configured_model = model or None
        self.timeout = timeout
        self.adapter = LlamaCppProvider(
            Settings(
                provider_url=base_url,
                timeout_seconds=timeout,
                health_timeout_seconds=10,
                max_input_bytes=65536,
                max_response_bytes=1048576,
                max_output_bytes=MAX_OUTPUT_BYTES,
            ),
            transport,
        )

    async def aclose(self):
        await self.adapter.close()

    async def resolve(self) -> ModelIdentity:
        try:
            models = await self.adapter.available_models()
        except ProviderError as exc:
            raise provider_error(exc) from None
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
        await self.validate(request)
        try:
            result = await self.adapter.infer(
                MessageInferenceRequest(
                    model_id="console",
                    messages=request.messages,
                    max_output_tokens=4096,
                    timeout_seconds=self.timeout,
                ),
                request.identity.model,
            )
        except ProviderError as exc:
            raise provider_error(exc) from None
        if result.finish_reason != "stop":
            raise IntelligenceError("incomplete_output")
        if not result.text.strip():
            raise IntelligenceError("invalid_response")
        return ExecutionResult(
            request.identity, result.text, usage=result.usage.model_dump() if result.usage else None
        )

    async def validate(self, request: ExecutionRequest):
        validate_messages(request.messages)
        if request.identity.provider != "llama.cpp" or (
            self.configured_model is not None and request.identity.model != self.configured_model
        ):
            raise IntelligenceError("model_mismatch")
