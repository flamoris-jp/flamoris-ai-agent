"""Explicit opt-in shared service using immutable authorized principal bindings."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import anyio
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    ValidationError,
    field_validator,
)

from flamoris_ai_agent.availability import AvailabilityProbe
from flamoris_ai_agent.delegation import authenticated_delegator
from flamoris_ai_agent.execution import IntelligenceError
from flamoris_ai_agent.mcp_service import AgentService, AskRequest
from flamoris_ai_agent.mcp_store import MCPStore
from flamoris_ai_agent.model_settings import ModelSettings, registry
from flamoris_ai_agent.personality import (
    PersonalityRead,
    PersonalitySave,
    PersonalityStore,
    load_context,
)
from flamoris_ai_agent.principals import PrincipalKeys, PrincipalSessions
from flamoris_ai_agent.runtime import configured_session
from flamoris_ai_agent.studio_context import StudioContext


class OpenSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    human: StrictStr
    agent: StrictStr
    project: StrictStr


class SettingsOpenRequest(OpenSessionRequest):
    model_id: StrictStr | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    remote_consent: StrictBool = False


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: StrictStr

    @field_validator("session_id")
    @classmethod
    def session_uuid(cls, value):
        return str(UUID(value))


class ContinueSessionRequest(SessionRequest):
    request_id: StrictStr
    model_id: StrictStr = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    remote_consent: StrictBool = False

    @field_validator("request_id")
    @classmethod
    def request_uuid(cls, value):
        return str(UUID(value))


class ScopedAskRequest(AskRequest):
    session_id: StrictStr
    context: StudioContext | None = None

    @field_validator("session_id")
    @classmethod
    def session_uuid(cls, value):
        return str(UUID(value))


class ScopedAgentService(AgentService):
    shared_principals = True

    def __init__(self, principals=None, scoped_session_factory=None, availability_probe=None):
        super().__init__()
        self.principals = principals or PrincipalSessions()
        self.settings_enabled = os.getenv("AGENT_SETTINGS_ENABLED") == "1"
        self.models = ModelSettings(self.principals) if self.settings_enabled else None
        self.personalities = PersonalityStore(self.principals) if self.settings_enabled else None
        self.scoped_session_factory = scoped_session_factory or self._configured
        self.availability_probe = availability_probe or AvailabilityProbe(
            self.principals, self.models
        )
        self.probing = False
        self.settings_active = 0
        self.continuing = False
        self.continuation_task = None

    async def aclose(self):
        self.closing = True
        # A handoff may already have committed. Drain its DB transaction instead
        # of abandoning it while the process tears down its authority.
        task = self.continuation_task
        if task is not None:
            await asyncio.shield(asyncio.gather(task, return_exceptions=True))
        await super().aclose()

    async def continue_session(self, raw):
        caller = authenticated_delegator.get()
        if caller is None or not self.models or self.closing:
            return {"ok": False, "error": {"code": "principal_unavailable"}}
        if self.active is not None or self.probing or self.continuing:
            return {"ok": False, "error": {"code": "busy"}}
        self.continuing = True
        try:
            request = ContinueSessionRequest.model_validate(raw)
            option = registry().get(request.model_id)
            if option is None:
                raise IntelligenceError("model_forbidden")
            if option.target.data_flow == "remote_authorized" and not request.remote_consent:
                raise IntelligenceError("remote_consent_required")

            def transition():
                # Deterministic handoff ID makes retry after lost acknowledgement
                # read the same selection. Old sessions are never retargeted.
                from uuid import NAMESPACE_URL, uuid5

                identity = uuid5(
                    NAMESPACE_URL,
                    f"flamoris-handoff:{caller}:{request.session_id}:{request.request_id}",
                )
                with self.principals.connection_factory() as conn:
                    exists = conn.execute(
                        "SELECT id FROM chat.principal_sessions WHERE id=%s", (identity,)
                    ).fetchone()
                if exists:
                    bound = self.principals.require(caller, identity)
                else:
                    source = self.principals.require(caller, request.session_id)
                    self.models.require(source)
                    bound = self.principals.open(
                        caller,
                        source.keys,
                        continue_from=source.session_id,
                        request_id=request.request_id,
                        configure=lambda conn, binding: self.models.bind_on(
                            conn, binding, request.model_id, request.remote_consent
                        ),
                    )
                if self.models.require(bound) != option:
                    raise IntelligenceError("session_continuation_changed")
                return bound

            self.continuation_task = asyncio.create_task(anyio.to_thread.run_sync(transition))
            try:
                bound = await asyncio.shield(self.continuation_task)
            except BaseException:
                with anyio.CancelScope(shield=True):
                    await self.continuation_task
                raise
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
        finally:
            self.continuation_task = None
            self.continuing = False

    def _configured(self, request, binding):
        option = self.models.require(binding) if self.models else None
        return configured_session(
            store=MCPStore(
                request, binding=binding, principals=self.principals, model_option=option
            ),
            context_loader=lambda: load_context(binding.keys.agent),
            target=option.target if option else None,
            context=request.context,
        )

    async def settings_operation(self, operation, raw):
        caller = authenticated_delegator.get()
        if caller is None or not self.settings_enabled or self.closing:
            return {"ok": False, "error": {"code": "principal_unavailable"}}
        if self.settings_active >= 2:
            return {"ok": False, "error": {"code": "busy"}}
        self.settings_active += 1
        try:
            if operation == "models":
                request = OpenSessionRequest.model_validate(raw)
                keys = PrincipalKeys(request.human, request.agent, request.project)
                data = await anyio.to_thread.run_sync(self.models.list, caller, keys)
            else:
                model = PersonalitySave if operation == "save" else PersonalityRead
                request = model.model_validate(raw)
                data = await anyio.to_thread.run_sync(
                    getattr(self.personalities, operation), caller, request
                )
            return {"ok": True, **data}
        except IntelligenceError as exc:
            return {"ok": False, "error": {"code": exc.code}}
        except (ValidationError, ValueError, TypeError, UnicodeError):
            return {"ok": False, "error": {"code": "invalid_input"}}
        except Exception:
            return {"ok": False, "error": {"code": "settings_unavailable"}}
        finally:
            self.settings_active -= 1

    async def availability(self, raw):
        caller = authenticated_delegator.get()
        if caller is None:
            return {"ok": False, "error": {"code": "principal_unavailable"}}
        try:
            request = SessionRequest.model_validate(raw)
            binding = await anyio.to_thread.run_sync(
                self.principals.require, caller, request.session_id
            )
            if self.models:
                await anyio.to_thread.run_sync(self.models.require, binding)
        except (ValidationError, ValueError, TypeError):
            return {"ok": False, "error": {"code": "invalid_input"}}
        except Exception:
            return {"ok": False, "error": {"code": "principal_unavailable"}}

        def observed(state, reason):
            now = datetime.now(UTC)
            return {
                "ok": True,
                "available": state == "ready",
                "state": state,
                "reason": reason,
                "observed_at": now.isoformat(),
                "expires_at": (now + timedelta(seconds=5)).isoformat(),
                "principal_revision": 1,
                "context_revisions": [1],
                "proposal_revisions": [],
            }

        if self.closing:
            return observed("unavailable", "shutting_down")
        if self.active is not None or self.probing or self.continuing:
            return observed("busy", "busy")
        self.probing = True
        try:
            async with asyncio.timeout(15):
                await self.availability_probe(binding)
                current = await anyio.to_thread.run_sync(
                    self.principals.require, caller, request.session_id
                )
                if current != binding:
                    raise IntelligenceError("principal_unavailable")
            if self.closing:
                return observed("unavailable", "shutting_down")
            if self.active is not None:
                return observed("busy", "busy")
            return observed("ready", "prerequisites_checked")
        except IntelligenceError as exc:
            if exc.code == "dependencies_unknown":
                return observed("unknown", "dependencies_unknown")
            if exc.code in {"provider_unavailable", "provider_timeout", "timeout"}:
                return observed("offline", "intelligence_unavailable")
            return observed("unavailable", "prerequisite_unavailable")
        except Exception:
            return observed("unavailable", "prerequisite_unavailable")
        finally:
            self.probing = False

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
            request = (
                SettingsOpenRequest if self.settings_enabled else OpenSessionRequest
            ).model_validate(raw)
            keys = PrincipalKeys(request.human, request.agent, request.project)
            if self.models:
                bound = await anyio.to_thread.run_sync(
                    lambda: self.principals.open(
                        caller,
                        keys,
                        configure=lambda conn, binding: self.models.bind_on(
                            conn, binding, request.model_id, request.remote_consent
                        ),
                    )
                )
            else:
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
        if self.active is not None or self.continuing:
            return {"ok": False, "error": {"code": "busy"}}
        try:
            binding = await anyio.to_thread.run_sync(
                self.principals.require, caller, request.session_id
            )
            if self.models:
                await anyio.to_thread.run_sync(self.models.require, binding)
        except IntelligenceError as exc:
            return {"ok": False, "error": {"code": exc.code}}
        except Exception:
            return {"ok": False, "error": {"code": "principal_unavailable"}}
        # After the probe await, the ordinary _run authority rechecks busy/closing
        # atomically before creating a request-specific AgentSession.
        if self.continuing:
            return {"ok": False, "error": {"code": "busy"}}
        result = await self._run(request, lambda req: self.scoped_session_factory(req, binding))
        return {**result, "session_id": request.session_id}
