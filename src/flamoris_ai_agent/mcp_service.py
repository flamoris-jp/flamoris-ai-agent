"""Single-principal, one-turn MCP operations; all conversation work uses AgentSession."""

import asyncio
from uuid import UUID

import anyio
from pydantic import BaseModel, ConfigDict, StrictStr, ValidationError, field_validator

from flamoris_ai_agent.execution import MAX_USER_BYTES, IntelligenceError
from flamoris_ai_agent.mcp_store import MCPStore
from flamoris_ai_agent.runtime import configured_session


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: StrictStr
    text: StrictStr
    previous_conversation_id: StrictStr | None = None

    @field_validator("request_id", "previous_conversation_id")
    @classmethod
    def uuid_string(cls, value):
        if value is None:
            return None
        return str(UUID(value))

    @field_validator("text")
    @classmethod
    def bounded_text(cls, value):
        if not value.strip() or len(value.encode()) > MAX_USER_BYTES:
            raise ValueError("invalid_input")
        return value


class AgentService:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or (
            lambda request: configured_session(store=MCPStore(request))
        )
        self.active = None
        self.closing = False

    def health(self):
        return {
            "ok": not self.closing,
            "alive": True,
            "busy": self.active is not None,
            "dependencies": "not_checked",
        }

    async def ask(self, raw):
        try:
            request = AskRequest.model_validate(raw)
        except (ValidationError, ValueError, TypeError):
            return {"ok": False, "error": {"code": "invalid_input"}}
        if self.closing:
            return {"ok": False, "error": {"code": "shutting_down"}}
        if self.active is not None:
            return {"ok": False, "error": {"code": "busy"}}
        self.active = asyncio.current_task()
        session = None
        response = None
        try:
            session = self.session_factory(request)
            await session.start(load_previous=False)
            result = await session.ask(request.text, metadata={"request_id": request.request_id})
            response = {
                "ok": True,
                "request_id": request.request_id,
                "conversation_id": str(session.conversation_id),
                "text": result.text,
                "provenance": {
                    "provider": result.identity.provider,
                    "model": result.identity.model,
                },
            }
        except IntelligenceError as exc:
            response = {"ok": False, "error": {"code": exc.code}, "request_id": request.request_id}
        except Exception:
            response = {
                "ok": False,
                "error": {"code": "internal_error"},
                "request_id": request.request_id,
            }
        finally:
            try:
                if session is not None:
                    # MCP cancellation uses an AnyIO cancel scope. Drain cleanup even
                    # when that scope is cancelled; DB calls have their own timeouts.
                    with anyio.CancelScope(shield=True):
                        try:
                            await session.aclose()
                        except Exception:
                            response = {
                                "ok": False,
                                "error": {"code": "cleanup_failed"},
                                "request_id": request.request_id,
                            }
            finally:
                self.active = None
        return response

    async def aclose(self):
        self.closing = True
        task = self.active
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
