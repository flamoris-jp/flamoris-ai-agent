"""Settings authority/revision acceptance in the existing disposable PostgreSQL CI DB."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from test_principals_postgres import DSN, authorization, database
from test_settings import option

from flamoris_ai_agent.execution import IntelligenceError
from flamoris_ai_agent.model_settings import ModelSettings
from flamoris_ai_agent.personality import (
    PersonalityRead,
    PersonalitySave,
    PersonalityStore,
    import_personality,
)
from flamoris_ai_agent.principals import PrincipalKeys

pytestmark = pytest.mark.skipif(
    not DSN, reason="disposable PostgreSQL test database not configured"
)
# Import fixtures intentionally: each case gets independent users/Agent/grants.
__all__ = ["authorization", "database"]


@pytest.fixture
def settings_db(authorization, monkeypatch):
    principals, dsn, ids = authorization
    monkeypatch.setenv("AGENT_CONTEXT_SOURCE", "db")
    monkeypatch.setenv("AGENT_INTELLIGENCE_TARGETS", json.dumps([option(), option("openai")]))
    first, second, agent, project = ids
    with psycopg.connect(dsn, autocommit=True) as conn:
        migration = (
            Path(__file__).resolve().parents[1] / "db/migrations/004_assistant_settings.sql"
        ).read_text()
        conn.execute(migration)
        conn.execute(migration)
        conn.execute("RESET ROLE")
        import_personality(conn, "helper", "Helper", [{"title": "Identity", "content": "original"}])
        conn.execute(
            "INSERT INTO core.personality_grants "
            "(delegator_key,human_id,agent_id,can_read,can_edit) "
            "VALUES ('backend',%s,%s,true,true)",
            (first, agent),
        )
        conn.execute(
            "INSERT INTO core.personality_grants "
            "(delegator_key,human_id,agent_id,can_read,can_edit) "
            "VALUES ('backend',%s,%s,true,false)",
            (second, agent),
        )
        for public in ["local", "api"]:
            spec = option("openai" if public == "api" else "llamacpp")
            model = conn.execute(
                "INSERT INTO runtime.models(model_key,provider,model_name) VALUES (%s,%s,%s) "
                "ON CONFLICT(model_key) DO UPDATE SET enabled=true RETURNING id",
                (spec["model_key"], spec["target"]["db_provider"], spec["target"]["db_model_name"]),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO core.model_grants "
                "(delegator_key,human_id,agent_id,project_id,model_id,allow_remote) "
                "VALUES ('backend',%s,%s,%s,%s,%s)",
                (first, agent, project, model, public == "api"),
            )
    bound = principals.open("backend", PrincipalKeys("first", "helper", "project"))
    other = principals.open("backend", PrincipalKeys("second", "helper", "project"))
    return principals, dsn, ids, bound, other


def update(bound, expected=1, request_id=None, text="new"):
    return PersonalitySave(
        session_id=str(bound.session_id),
        request_id=request_id or str(uuid4()),
        expected_revision=expected,
        display_name="New Helper",
        sections=[{"title": "Identity", "content": text}],
    )


def test_editor_permission_revision_history_and_duplicate_fence(settings_db):
    principals, dsn, ids, bound, other = settings_db
    store = PersonalityStore(principals)
    assert store.get("backend", PersonalityRead(session_id=str(bound.session_id)))["can_edit"]
    assert not store.get("backend", PersonalityRead(session_id=str(other.session_id)))["can_edit"]
    with pytest.raises(IntelligenceError, match="personality_forbidden"):
        store.save("backend", update(other))
    first = update(bound)
    assert store.save("backend", first) == {"revision": 2, "duplicate": False}
    assert store.save("backend", update(bound, 2))["revision"] == 3
    assert store.save("backend", first) == {"revision": 2, "duplicate": True}
    assert store.get("backend", PersonalityRead(session_id=str(bound.session_id)))["revision"] == 3
    with pytest.raises(IntelligenceError, match="update_identity_mismatch"):
        store.save("backend", first.model_copy(update={"display_name": "tampered"}))
    history = store.history(
        "backend", PersonalityRead(session_id=str(bound.session_id), before_revision=2)
    )
    assert history["versions"][0]["sections"] == [{"title": "Identity", "content": "original"}]
    assert store.save("backend", update(bound, 3, text="original"))["revision"] == 4
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("UPDATE core.personality_grants SET enabled=false")
    with pytest.raises(IntelligenceError, match="personality_forbidden"):
        store.get("backend", PersonalityRead(session_id=str(bound.session_id)))


def test_concurrent_updates_commit_once_and_conflict(settings_db):
    principals, _, _, bound, _ = settings_db
    store = PersonalityStore(principals)

    def save(req):
        try:
            return store.save("backend", req)["revision"]
        except IntelligenceError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(save, [update(bound, text="first"), update(bound, text="second")]))
    assert sorted(map(str, values)) == ["2", "revision_conflict"]


def test_model_grants_remote_consent_changed_config_and_retention(settings_db, monkeypatch):
    principals, dsn, ids, bound, other = settings_db
    settings = ModelSettings(principals)
    assert {m["id"] for m in settings.list("backend", bound.keys)["models"]} == {"local", "api"}
    assert settings.list("backend", other.keys)["models"] == []
    with pytest.raises(IntelligenceError, match="remote_consent_required"):
        principals.open(
            "backend", bound.keys, configure=lambda c, b: settings.bind_on(c, b, "api", False)
        )
    selected = principals.open(
        "backend", bound.keys, configure=lambda c, b: settings.bind_on(c, b, "api", True)
    )
    assert settings.require(selected).id == "api"
    with principals.connection_factory() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE core.model_grants SET allow_remote=true")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE chat.principal_options SET public_model_id='local'")
    changed = option("openai")
    changed["target"]["max_output_tokens"] = 512
    monkeypatch.setenv("AGENT_INTELLIGENCE_TARGETS", json.dumps([option(), changed]))
    with pytest.raises(IntelligenceError, match="model_selection_changed"):
        settings.require(selected)
    monkeypatch.setenv("AGENT_INTELLIGENCE_TARGETS", json.dumps([option(), option("openai")]))
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("UPDATE core.model_grants SET enabled=false")
    with pytest.raises(IntelligenceError, match="model_forbidden"):
        settings.require(selected)


def test_import_preserves_order_body_and_existing_identity(settings_db):
    principals, dsn, ids, bound, _ = settings_db
    with psycopg.connect(dsn, autocommit=True) as conn:
        assert (
            conn.execute("SELECT id FROM core.agents WHERE agent_key='helper'").fetchone()[0]
            == ids[2]
        )
        with pytest.raises(IntelligenceError, match="revision_conflict"):
            import_personality(
                conn, "helper", "Replacement", [{"title": "Changed", "content": "bad"}]
            )
    assert PersonalityStore(principals).get(
        "backend", PersonalityRead(session_id=str(bound.session_id))
    )["sections"] == [{"title": "Identity", "content": "original"}]
