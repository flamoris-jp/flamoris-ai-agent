"""Read-only prerequisite probe; never starts a conversation, inference or runtime."""

import os

import anyio

from flamoris_ai_agent import db, prompts
from flamoris_ai_agent.config import load_agent_context
from flamoris_ai_agent.execution import ExecutionRequest, IntelligenceError, validate_messages
from flamoris_ai_agent.runtime import configured_session


class AvailabilityProbe:
    def __init__(self, principals):
        self.principals = principals

    async def __call__(self, binding):
        if os.getenv("AGENT_INTELLIGENCE_TRANSPORT", "direct") != "mcp":
            raise IntelligenceError("dependencies_unknown")
        # Construct configuration/client only. AgentSession.start/ask are never called.
        session = configured_session(context_loader=lambda: load_agent_context(binding.keys.agent))
        try:
            context = session.context_loader()
            identity = await session.client.resolve()
            messages = prompts.build_messages(prompts.build_system_prompt(context), [])
            validate_messages(messages)
            await session.client.validate(ExecutionRequest(identity, messages))
            await anyio.to_thread.run_sync(self._database, binding, identity)
        finally:
            await session.client.aclose()

    def _database(self, binding, identity):
        with self.principals.connection_factory() as conn:
            current = self.principals.require_on(conn, binding.delegator, binding.session_id)
            if current != binding:
                raise IntelligenceError("principal_unavailable")
            refs = db.load_runtime_refs(conn, principal=binding.keys)
            if any(refs[name] != value for name, value in binding.ids.items()):
                raise IntelligenceError("principal_unavailable")
            db.validate_model_ref(conn, refs["model_id"], identity.model, identity.provider)
