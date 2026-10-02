"""Transport-owned caller context; never resolved from model/tool arguments."""

from contextvars import ContextVar

authenticated_delegator: ContextVar[str | None] = ContextVar(
    "agent_authenticated_delegator", default=None
)
