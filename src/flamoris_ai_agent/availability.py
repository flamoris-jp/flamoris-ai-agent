"""Read-only prerequisite probe; never starts a conversation, inference or runtime."""

import os

import anyio

from flamoris_ai_agent import db, prompts
from flamoris_ai_agent.execution import ExecutionRequest, IntelligenceError, validate_messages
from flamoris_ai_agent.personality import load_context
from flamoris_ai_agent.runtime import configured_session


class AvailabilityProbe:
    def __init__(self, principals, model_settings=None):
        self.principals = principals
        self.model_settings = model_settings

    async def __call__(self, binding):
        if os.getenv("AGENT_INTELLIGENCE_TRANSPORT", "direct") != "mcp":
            raise IntelligenceError("dependencies_unknown")
        # Construct configuration/client only. AgentSession.start/ask are never called.
        option = self.model_settings.require(binding) if self.model_settings else None
        session = configured_session(
            context_loader=lambda: load_context(binding.keys.agent),
            target=option.target if option else None,
        )
        try:
            context = session.context_loader()
            identity = await session.client.resolve()
            messages = prompts.build_messages(prompts.build_system_prompt(context), [])
            validate_messages(messages)
            await session.client.validate(ExecutionRequest(identity, messages))
            await anyio.to_thread.run_sync(self._database, binding, identity, option)
        finally:
            await session.client.aclose()

    def _database(self, binding, identity, option=None):
        with self.principals.connection_factory() as conn:
            current = self.principals.require_on(conn, binding.delegator, binding.session_id)
            if current != binding:
                raise IntelligenceError("principal_unavailable")
            refs = db.load_runtime_refs(
                conn, principal=binding.keys, model_key=option.model_key if option else None
            )
            if any(refs[name] != value for name, value in binding.ids.items()):
                raise IntelligenceError("principal_unavailable")
            db.validate_model_ref(conn, refs["model_id"], identity.model, identity.provider)
