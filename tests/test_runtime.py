import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from flamoris_ai_agent import chat
from flamoris_ai_agent.config import AgentContextError
from flamoris_ai_agent.execution import ExecutionResult, IntelligenceError, ModelIdentity
from flamoris_ai_agent.runtime import AgentSession, PostgresStore

CONTEXT = [{"title": "Identity", "file": "identity.md", "content": "identity"}]
IDENTITY = ModelIdentity("fake", "served")


def session():
    store = Mock()
    store.open.return_value = {
        "conversation_id": "old",
        "messages": [{"sender": "Example User", "content": "old story"}],
    }
    store.start.return_value = ("conversation", "instance")
    client = AsyncMock()
    client.resolve.return_value = IDENTITY
    client.execute.return_value = ExecutionResult(IDENTITY, "answer")
    return AgentSession(client, store, context_loader=lambda: CONTEXT)


def test_identity_context_writes_and_shutdown():
    async def run():
        s = session()
        await s.start(load_previous=True)
        await s.ask("hello")
        assert "old story" not in s.store.start.call_args.args[0]
        assert "old story" in s.client.execute.call_args.args[0].messages[1]["content"]
        assert s.store.start.call_args.args[1]["previous_conversation"] == s.previous
        assert s.store.start.call_args.args[1]["agent_sections"] == CONTEXT
        assert [c.args[0] for c in s.store.save.call_args_list] == ["user", "assistant"]
        assert s.store.save.call_args_list[-1].args[2] == {
            "intelligence_model": "served",
            "intelligence_provider": "fake",
        }
        await s.aclose()
        await s.aclose()
        s.store.close.assert_called_once()
        s.client.aclose.assert_awaited_once()

    asyncio.run(run())


@pytest.mark.parametrize("error", [IntelligenceError("timeout"), asyncio.CancelledError()])
def test_failed_turn_keeps_user_only(error):
    async def run():
        s = session()
        s.client.execute.side_effect = error
        await s.start()
        with pytest.raises(type(error)):
            await s.ask("hello")
        assert s.store.save.call_count == 1
        assert s.history == [{"role": "user", "content": "hello"}]
        assert not s.busy
        await s.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("failure_at", ["user", "assistant"])
def test_ambiguous_persistence_poison_session(failure_at):
    async def run():
        s = session()

        def save(role, text, metadata):
            if role == failure_at:
                raise RuntimeError("secret database details")

        s.store.save.side_effect = save
        await s.start()
        with pytest.raises(IntelligenceError, match="^persistence_failed$"):
            await s.ask("hello")
        assert s.failed
        assert not any(m["role"] == "assistant" for m in s.history)
        with pytest.raises(IntelligenceError, match="invalid_lifecycle"):
            await s.ask("do not retry")
        await s.aclose()

    asyncio.run(run())


def test_start_failure_always_closes_resources():
    async def run():
        s = session()
        s.store.start.side_effect = RuntimeError("secret")
        with pytest.raises(IntelligenceError, match="^startup_failed$"):
            await s.start()
        await s.aclose()
        s.store.close.assert_called_once()
        s.client.aclose.assert_awaited_once()

    asyncio.run(run())


def test_invalid_context_has_distinct_startup_code():
    async def run():
        s = session()
        s.context_loader = lambda: (_ for _ in ()).throw(AgentContextError("missing manifest"))
        with pytest.raises(IntelligenceError, match="^invalid_agent_context$"):
            await s.start()
        s.client.resolve.assert_not_awaited()
        await s.aclose()

    asyncio.run(run())


def test_cleanup_failure_is_not_success():
    async def run():
        s = session()
        await s.start()
        s.store.close.side_effect = RuntimeError("secret")
        with pytest.raises(IntelligenceError, match="^cleanup_failed$"):
            await s.aclose()
        s.client.aclose.assert_awaited_once()

    asyncio.run(run())


def test_busy_and_model_mismatch():
    async def run():
        s = session()
        await s.start()
        s.busy = True
        with pytest.raises(IntelligenceError, match="busy"):
            await s.ask("hello")
        s.busy = False
        s.client.execute.return_value = ExecutionResult(ModelIdentity("other", "model"), "text")
        with pytest.raises(IntelligenceError, match="model_mismatch"):
            await s.ask("hello")
        assert s.store.save.call_count == 1
        await s.aclose()

    asyncio.run(run())


def test_console_uses_same_session():
    s = session()
    with (
        patch.object(chat, "configured_session", return_value=s),
        patch("builtins.input", side_effect=["hello", "/bye"]),
    ):
        chat.main()
    s.client.execute.assert_awaited_once()
    s.store.close.assert_called_once()


def test_start_transaction_rolls_back_instance_on_conversation_failure():
    store = PostgresStore()
    store.conn = MagicMock()
    store.refs = {"agent_id": "unchanged"}
    with (
        patch("flamoris_ai_agent.db.start_instance", return_value="i"),
        patch("flamoris_ai_agent.db.start_conversation", side_effect=RuntimeError("DB")),
    ):
        with pytest.raises(RuntimeError):
            store.start("policy", {})
    assert store.instance_id is None and store.runtime is None
    assert store.conn.transaction.return_value.__exit__.call_args.args[0] is RuntimeError


def test_history_is_bounded():
    async def run():
        s = session()
        await s.start()
        for _ in range(50):
            await s.ask("hello")
        assert len(s.history) <= 16
        await s.aclose()

    asyncio.run(run())


async def test_turn_reserves_admission_before_awaiting_client_validation():
    agent = session()
    await agent.start()
    validating = asyncio.Event()

    async def validate(_):
        validating.set()
        await asyncio.Event().wait()

    agent.client.validate.side_effect = validate
    first = asyncio.create_task(agent.ask("first"))
    await asyncio.wait_for(validating.wait(), 1)
    with pytest.raises(IntelligenceError, match="busy"):
        await agent.ask("second")
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    agent.store.save.assert_not_called()
    assert agent.busy is False
    await agent.aclose()
