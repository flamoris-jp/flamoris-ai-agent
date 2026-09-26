"""Agent-facing inference contract; no provider or persistence implementation."""

from dataclasses import dataclass
from typing import Protocol


class IntelligenceError(RuntimeError):
    """Only fixed, non-sensitive error codes cross this boundary."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ModelIdentity:
    provider: str
    model: str


@dataclass(frozen=True)
class ExecutionRequest:
    identity: ModelIdentity
    messages: list[dict[str, str]]


@dataclass(frozen=True)
class ExecutionResult:
    identity: ModelIdentity
    text: str


MAX_INPUT_BYTES = 65536
MAX_USER_BYTES = 16384
MAX_OUTPUT_BYTES = 65536


def validate_messages(messages):
    if not isinstance(messages, list) or not 1 <= len(messages) <= 128:
        raise IntelligenceError("invalid_input")
    size = 0
    for message in messages:
        if (
            not isinstance(message, dict)
            or set(message) != {"role", "content"}
            or message["role"] not in ("system", "user", "assistant")
            or not isinstance(message["content"], str)
        ):
            raise IntelligenceError("invalid_input")
        size += len(message["content"].encode("utf-8"))
    if size > MAX_INPUT_BYTES:
        raise IntelligenceError("input_too_large")


class ExecutionClient(Protocol):
    async def resolve(self) -> ModelIdentity: ...

    async def execute(self, request: ExecutionRequest) -> ExecutionResult: ...

    async def aclose(self) -> None: ...
