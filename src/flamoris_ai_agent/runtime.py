"""Shared conversation lifecycle. The CLI and MCP do not own separate state."""

import asyncio
import os

from flamoris_ai_agent import db, prompts
from flamoris_ai_agent.execution import (
    MAX_OUTPUT_BYTES,
    MAX_USER_BYTES,
    ExecutionClient,
    ExecutionRequest,
    IntelligenceError,
    validate_messages,
)
from flamoris_ai_agent.intelligence import IntelligenceClient


class PostgresStore:
    def __init__(self):
        self.conn = None
        self.runtime = None
        self.instance_id = None

    def open(self, identity, load_previous):
        self.conn = db.get_connection()
        self.refs = db.load_runtime_refs(self.conn)
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
        self, client: ExecutionClient, store, *, context_loader=prompts.load_system_context
    ):
        self.client, self.store = client, store
        self.context_loader = context_loader
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
            self.identity = await self.client.resolve()
            context = self.context_loader()
            self.previous = self.store.open(self.identity, load_previous)
            self.previous_text = prompts.format_previous_conversation(self.previous)
            self.policy = prompts.build_system_prompt(context)
            validate_messages(prompts.build_messages(self.policy, [], self.previous_text))
            self.conversation_id, self.instance_id = self.store.start(
                self.policy, prompts.json_safe({**context, "previous_conversation": self.previous})
            )
            self.started = True
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
        messages = prompts.build_messages(self.policy, history, self.previous_text)
        validate_messages(messages)
        self.busy = True
        try:
            self._save("user", text, metadata or {})
            self.history = history[-min(max(prompts.MAX_CONTEXT_MESSAGES, 1), 64) :]
            result = await self.client.execute(ExecutionRequest(self.identity, messages))
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
                },
            )
            self.history.append({"role": "assistant", "content": result.text})
            self.history = self.history[-min(max(prompts.MAX_CONTEXT_MESSAGES, 1), 64) :]
            return result
        finally:
            self.busy = False

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


def configured_session(*, store=None):
    return AgentSession(
        IntelligenceClient(
            os.getenv("INTELLIGENCE_BASE_URL", "http://127.0.0.1:8081"),
            os.getenv("INTELLIGENCE_MODEL"),
        ),
        store if store is not None else PostgresStore(),
    )
