"""Immutable handoffs and real scoped historical context, without provider calls."""

import asyncio

from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_internal_api import internal
from test_principals_postgres import DSN, authorization, database, scoped_store_open
from test_settings_postgres import settings_db

from flamoris_ai_agent.delegation import authenticated_delegator
from flamoris_ai_agent.execution import IntelligenceError
from flamoris_ai_agent.model_settings import ModelSettings
from flamoris_ai_agent.scoped_service import ScopedAgentService

pytestmark = pytest.mark.skipif(not DSN, reason="disposable PostgreSQL not configured")
__all__ = ["authorization", "database", "settings_db"]


def selected(principals, keys, model="local", consent=False):
    settings = ModelSettings(principals)
    return principals.open(
        "backend", keys, configure=lambda c, b: settings.bind_on(c, b, model, consent)
    )


def handoff(principals, source, request, model="api", consent=True):
    settings = ModelSettings(principals)
    return principals.open(
        "backend",
        source.keys,
        continue_from=source.session_id,
        request_id=request,
        configure=lambda c, b: settings.bind_on(c, b, model, consent),
    )


def seed(dsn, bound, *, complete=True):
    parent = uuid4()
    context = {
        "agent_sections": [{"title": "Identity", "content": "original persona"}],
        "personality_revision": 1,
        "previous_conversation": {
            "messages": [{"role": "user", "sender": "first", "content": "earlier turn"}]
        },
        "studio_context": {"draft": {"positive_prompt": "earlier attachment"}},
    }
    with psycopg.connect(dsn, autocommit=True) as conn:
        from flamoris_ai_agent.mcp_store import scope_id

        conn.execute(
            "INSERT INTO chat.conversations"
            "(id,project_id,primary_agent_id,status,ended_at,system_context,metadata) "
            "VALUES (%s,%s,%s,'closed',now(),%s,%s)",
            (
                parent,
                bound.project_id,
                bound.agent_id,
                Jsonb(context),
                Jsonb(
                    {
                        "client": "agent-mcp",
                        "scope": scope_id(bound.ids),
                        "principal_session": str(bound.session_id),
                        "model_selection": {"id": "local"},
                    }
                ),
            ),
        )
        conn.execute(
            "INSERT INTO chat.participants(conversation_id,human_id,display_name) "
            "VALUES (%s,%s,'first')",
            (parent, bound.human_id),
        )
        for role, content in [
            ("user", "last question"),
            *([("assistant", "last answer")] if complete else []),
        ]:
            conn.execute(
                "INSERT INTO chat.messages(conversation_id,role,content) VALUES (%s,%s,%s)",
                (parent, role, content),
            )
    return parent


def test_handoff_preserves_identity_history_persona_and_duplicate_ack(settings_db):
    principals, dsn, _, bound, other = settings_db
    source = selected(principals, bound.keys)
    parent = seed(dsn, source)
    request = uuid4()
    target = handoff(principals, source, request)
    assert target.ids == source.ids and target.session_id != source.session_id
    assert ModelSettings(principals).require(target).id == "api"
    assert handoff(principals, source, request) == target
    with pytest.raises(IntelligenceError, match="session_continuation_changed"):
        handoff(principals, source, uuid4())
    with pytest.raises(IntelligenceError, match="principal_unavailable"):
        principals.require("backend", source.session_id)
    store, previous = scoped_store_open(principals, target, parent)
    try:
        assert [m["content"] for m in previous["messages"]][-2:] == ["last question", "last answer"]
        assert previous["messages"][0]["content"] == "earlier turn"
        assert "earlier attachment" in previous["messages"][1]["content"]
        assert (
            store.restore_context(lambda: pytest.fail("persona must be restored"))[0]["content"]
            == "original persona"
        )
    finally:
        store.close()
    for isolated in (other, selected(principals, source.keys)):
        with pytest.raises(IntelligenceError, match="conversation_unavailable"):
            scoped_store_open(principals, isolated, parent)
    with psycopg.connect(dsn) as conn:
        assert conn.execute(
            "SELECT metadata->'model_selection'->>'id' FROM chat.conversations WHERE id=%s",
            (parent,),
        ).fetchone() == ("local",)
        assert conn.execute(
            "SELECT public_model_id FROM chat.principal_options WHERE session_id=%s",
            (source.session_id,),
        ).fetchone() == ("local",)


def test_incomplete_source_and_missing_consent_leave_old_authority(settings_db):
    principals, dsn, _, bound, _ = settings_db
    source = selected(principals, bound.keys)
    with pytest.raises(IntelligenceError, match="remote_consent_required"):
        handoff(principals, source, uuid4(), consent=False)
    parent = seed(dsn, source, complete=False)
    with pytest.raises(IntelligenceError, match="conversation_incomplete"):
        handoff(principals, source, uuid4())
    assert principals.require("backend", source.session_id) == source
    with psycopg.connect(dsn) as conn:
        assert conn.execute("SELECT count(*) FROM chat.principal_continuations").fetchone() == (0,)
        assert conn.execute(
            "SELECT count(*) FROM chat.messages WHERE conversation_id=%s", (parent,)
        ).fetchone() == (1,)


async def test_http_domain_retry_rejects_changed_target_and_revoked_grants(
    settings_db, monkeypatch
):
    principals, dsn, _, bound, _ = settings_db
    monkeypatch.setenv("AGENT_SETTINGS_ENABLED", "1")
    source = selected(principals, bound.keys)
    service = ScopedAgentService(principals)
    raw = {
        "session_id": str(source.session_id),
        "request_id": str(uuid4()),
        "model_id": "api",
        "remote_consent": True,
    }
    token = authenticated_delegator.set("backend")
    try:
        answer = await service.continue_session(raw)
        assert answer["ok"]
        assert await service.continue_session(raw) == answer
        changed = await service.continue_session({**raw, "model_id": "local"})
        assert changed["error"]["code"] == "session_continuation_changed"
        service.active = object()
        assert (await service.continue_session(raw))["error"]["code"] == "busy"
        service.active = None
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute("UPDATE core.model_grants SET enabled=false")
        assert not (await service.continue_session(raw))["ok"]
    finally:
        authenticated_delegator.reset(token)
        await service.aclose()


async def test_continuation_http_contract_and_failed_shutdown_drain(settings_db, monkeypatch):
    principals, _, _, bound, _ = settings_db
    monkeypatch.setenv("AGENT_SETTINGS_ENABLED", "1")
    source = selected(principals, bound.keys)
    service = ScopedAgentService(principals)
    raw = {
        "session_id": str(source.session_id),
        "request_id": str(uuid4()),
        "model_id": "api",
        "remote_consent": True,
    }
    async with internal(service) as client:
        capabilities = (await client.get("/api/v1/capabilities")).json()
        assert "sessions.continue" in capabilities["operations"]
        result = (await client.post("/api/v1/sessions/continue", json=raw)).json()
        assert result["ok"] and result["session_id"] != raw["session_id"]
        assert (await client.post("/api/v1/sessions/continue", json=raw)).json() == result

    async def failed_transaction():
        raise IntelligenceError("model_forbidden")

    service.continuation_task = asyncio.create_task(failed_transaction())
    await service.aclose()
    assert service.closing
