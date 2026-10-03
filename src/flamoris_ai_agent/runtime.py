"""Shared conversation lifecycle. The CLI and MCP do not own separate state."""

import asyncio
import json
import os

from flamoris_ai_agent import db, prompts
from flamoris_ai_agent.config import AgentContextError
from flamoris_ai_agent.execution import (
    MAX_OUTPUT_BYTES,
    MAX_USER_BYTES,
    ExecutionClient,
    ExecutionRequest,
    IntelligenceError,
    validate_messages,
)
from flamoris_ai_agent.intelligence import IntelligenceClient
from flamoris_ai_agent.studio_context import StudioContext


class PostgresStore:
    def __init__(self, refs_loader=None):
        self.conn = None
        self.runtime = None
        self.instance_id = None
        self.refs_loader = refs_loader

    def open(self, identity, load_previous):
        self.conn = db.get_connection()
        self.refs = (
            self.refs_loader(self.conn)
            if self.refs_loader is not None
            else db.load_runtime_refs(self.conn)
        )
        db.validate_model_ref(self.conn, self.refs["model_id"], identity.model, identity.provider)
        return (
            db.get_previous_conversation(
                self.conn,
                self.refs["agent_id"],
                self.refs["project_id"],
                message_limit=min(max(prompts.PREVIOUS_MESSAGE_LIMIT, 1), 64),
            )
            if load_previous and prompts.LOAD_PREVIOUS
            else None
        )

    def start(self, policy, context):
        with self.conn.transaction():
            instance = db.start_instance(self.conn, self.refs)
            runtime = db.start_conversation(self.conn, self.refs, instance, policy, context)
        self.instance_id, self.runtime = instance, runtime
        return runtime["conversation_id"], instance

    def save(self, role, text, metadata):
        db.save_message(
            self.conn,
            self.runtime["conversation_id"],
            self.runtime["human_participant_id" if role == "user" else "agent_participant_id"],
            role,
            text,
            self.instance_id,
            metadata=metadata,
        )

    def close(self):
        if self.conn is None:
            return
        try:
            if self.runtime is not None:
                db.close_runtime(
                    self.conn,
                    self.runtime["conversation_id"],
                    self.runtime["conversation_session_id"],
                    self.instance_id,
                )
        finally:
            self.conn.close()
            self.conn = None


class AgentSession:
    def __init__(
        self,
        client: ExecutionClient,
        store,
        *,
        context_loader=prompts.load_system_context,
        context: StudioContext | None = None,
    ):
        self.client, self.store = client, store
        self.context_loader = context_loader
        if context is not None and not isinstance(context, StudioContext):
            raise IntelligenceError("invalid_input")
        # Snapshot now: nested list mutation outside this session cannot alter
        # the admitted prompt or its durable request context after uncertainty.
        self.context_text = context.serialized() if context else None
        self.context_data = json.loads(self.context_text)["context"] if context else None
        self.history = []
        self.started = False
        self.failed = False
        self.closed = False
        self.busy = False
        self.previous = None
        self.conversation_id = None
        self.instance_id = None

    async def start(self, *, load_previous=False):
        if self.started or self.closed or self.failed:
            raise IntelligenceError("invalid_lifecycle")
        try:
            restore = getattr(type(self.store), "restore_context", None)
            context = self.context_loader() if restore is None else None
            self.identity = await self.client.resolve()
            self.previous = self.store.open(self.identity, load_previous)
            if restore is not None:
                context = restore(self.store, self.context_loader)
            self.previous_text = prompts.format_previous_conversation(self.previous)
            self.policy = prompts.build_system_prompt(context)
            validate_messages(self._messages([]))
            await self.client.validate(ExecutionRequest(self.identity, self._messages([])))
            self.conversation_id, self.instance_id = self.store.start(
                self.policy,
                prompts.json_safe(
                    {
                        "agent_sections": context,
                        "personality_revision": getattr(context, "revision", None),
                        "previous_conversation": self.previous,
                        **({"studio_context": self.context_data} if self.context_data else {}),
                    }
                ),
            )
            self.started = True
        except AgentContextError:
            self.failed = True
            raise IntelligenceError("invalid_agent_context") from None
        except IntelligenceError:
            self.failed = True
            raise
        except asyncio.CancelledError:
            self.failed = True
            raise
        except Exception:
            self.failed = True
            raise IntelligenceError("startup_failed") from None

    async def ask(self, text: str, *, metadata=None):
        if not self.started or self.closed or self.failed:
            raise IntelligenceError("invalid_lifecycle")
        if self.busy:
            raise IntelligenceError("busy")
        if not isinstance(text, str) or not text.strip() or len(text.encode()) > MAX_USER_BYTES:
            raise IntelligenceError("invalid_input")
        history = [*self.history, {"role": "user", "content": text}]
        messages = self._messages(history)
        validate_messages(messages)
        execution = ExecutionRequest(self.identity, messages)
        self.busy = True
        try:
            await self.client.validate(execution)
            self._save("user", text, metadata or {})
            self.history = history[-min(max(prompts.MAX_CONTEXT_MESSAGES, 1), 64) :]
            result = await self.client.execute(execution)
            if result.identity != self.identity:
                raise IntelligenceError("model_mismatch")
            if not isinstance(result.text, str) or not result.text.strip():
                raise IntelligenceError("invalid_response")
            if len(result.text.encode()) > MAX_OUTPUT_BYTES:
                raise IntelligenceError("output_too_large")
            self._save(
                "assistant",
                result.text,
                {
                    **(metadata or {}),
                    "intelligence_model": result.identity.model,
                    "intelligence_provider": result.identity.provider,
                    **({"intelligence_usage": result.usage} if result.usage else {}),
                    **(
                        {
                            "intelligence_public_model": result.public_identity.model,
                            "intelligence_public_provider": result.public_identity.provider,
                            "intelligence_execution_id": result.execution_id,
                        }
                        if result.public_identity
                        else {}
                    ),
                },
            )
            self.history.append({"role": "assistant", "content": result.text})
            self.history = self.history[-min(max(prompts.MAX_CONTEXT_MESSAGES, 1), 64) :]
            return result
        finally:
            self.busy = False

    def _messages(self, history):
        return prompts.build_messages(self.policy, history, self.previous_text, self.context_text)

    def _save(self, role, text, metadata):
        try:
            self.store.save(role, text, metadata)
        except Exception:
            self.failed = True
            raise IntelligenceError("persistence_failed") from None

    async def aclose(self):
        if self.closed:
            return
        self.closed = True
        try:
            try:
                self.store.close()
            except Exception:
                raise IntelligenceError("cleanup_failed") from None
        finally:
            await self.client.aclose()


def configured_session(
    *, store=None, context_loader=prompts.load_system_context, context=None, target=None
):
    mode = os.getenv("AGENT_INTELLIGENCE_TRANSPORT", "direct")
    if (context is not None or target is not None) and mode != "mcp":
        raise IntelligenceError("context_unavailable")
    if mode == "mcp":
        from flamoris_ai_agent.intelligence_mcp import ApprovedTarget, IntelligenceMCPClient

        try:
            selected = target is not None
            target = target or ApprovedTarget.model_validate(
                json.loads(os.environ["AGENT_INTELLIGENCE_TARGET"])
            )
            if not selected and target.data_flow != "local_only":
                raise IntelligenceError("remote_export_forbidden")
            client = IntelligenceMCPClient(os.environ["AGENT_INTELLIGENCE_MCP_ENDPOINT"], target)
        except (ValueError, TypeError, KeyError):
            raise IntelligenceError("invalid_intelligence_configuration") from None
    elif mode == "direct":
        client = IntelligenceClient(
            os.getenv("INTELLIGENCE_BASE_URL", "http://127.0.0.1:8081"),
            os.getenv("INTELLIGENCE_MODEL"),
        )
    else:
        raise IntelligenceError("invalid_intelligence_configuration")
    return AgentSession(
        client,
        store if store is not None else PostgresStore(),
        context_loader=context_loader,
        context=context,
    )
