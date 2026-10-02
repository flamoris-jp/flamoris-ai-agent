"""Explicit opt-in shared service using immutable authorized principal bindings."""

from uuid import UUID

import anyio
from pydantic import BaseModel, ConfigDict, StrictStr, ValidationError, field_validator

from flamoris_ai_agent.config import load_agent_context
from flamoris_ai_agent.delegation import authenticated_delegator
from flamoris_ai_agent.execution import IntelligenceError
from flamoris_ai_agent.mcp_service import AgentService, AskRequest
from flamoris_ai_agent.mcp_store import MCPStore
from flamoris_ai_agent.principals import PrincipalKeys, PrincipalSessions
from flamoris_ai_agent.runtime import configured_session


class OpenSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    human: StrictStr
    agent: StrictStr
    project: StrictStr


class ScopedAskRequest(AskRequest):
    session_id: StrictStr

    @field_validator("session_id")
    @classmethod
    def session_uuid(cls, value):
        return str(UUID(value))


class ScopedAgentService(AgentService):
    shared_principals = True

    def __init__(self, principals=None, scoped_session_factory=None):
        super().__init__()
        self.principals = principals or PrincipalSessions()
        self.scoped_session_factory = scoped_session_factory or self._configured

    def _configured(self, request, binding):
        return configured_session(
            store=MCPStore(request, binding=binding, principals=self.principals),
            context_loader=lambda: load_agent_context(binding.keys.agent),
        )

    async def ask(self, raw):
        # There is no fixed-principal fallback in shared mode, even if called
        # directly rather than through its separately versioned tool catalog.
        return {"ok": False, "error": {"code": "principal_required"}}

    async def open_session(self, raw):
        caller = authenticated_delegator.get()
        if caller is None:
            return {"ok": False, "error": {"code": "principal_unavailable"}}
        if self.closing:
            return {"ok": False, "error": {"code": "shutting_down"}}
        try:
            request = OpenSessionRequest.model_validate(raw)
            keys = PrincipalKeys(request.human, request.agent, request.project)
            bound = await anyio.to_thread.run_sync(self.principals.open, caller, keys)
            return {
                "ok": True,
                "session_id": str(bound.session_id),
                "expires_at": bound.expires_at.isoformat(),
                "principal_revision": 1,
            }
        except IntelligenceError as exc:
            return {"ok": False, "error": {"code": exc.code}}
        except (ValidationError, ValueError, TypeError):
            return {"ok": False, "error": {"code": "invalid_input"}}
        except Exception:
            return {"ok": False, "error": {"code": "principal_unavailable"}}

    async def ask_scoped(self, raw):
        caller = authenticated_delegator.get()
        if caller is None:
            return {"ok": False, "error": {"code": "principal_unavailable"}}
        try:
            request = ScopedAskRequest.model_validate(raw)
        except (ValidationError, ValueError, TypeError):
            return {"ok": False, "error": {"code": "invalid_input"}}
        if self.closing:
            return {"ok": False, "error": {"code": "shutting_down"}}
        if self.active is not None:
            return {"ok": False, "error": {"code": "busy"}}
        try:
            binding = await anyio.to_thread.run_sync(
                self.principals.require, caller, request.session_id
            )
        except IntelligenceError as exc:
            return {"ok": False, "error": {"code": exc.code}}
        except Exception:
            return {"ok": False, "error": {"code": "principal_unavailable"}}
        # After the probe await, the ordinary _run authority rechecks busy/closing
        # atomically before creating a request-specific AgentSession.
        result = await self._run(request, lambda req: self.scoped_session_factory(req, binding))
        return {**result, "session_id": request.session_id}
