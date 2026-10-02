"""Real authorization/migration checks against an explicitly disposable CI DB."""

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from flamoris_ai_agent.execution import IntelligenceError
from flamoris_ai_agent.principals import PrincipalKeys, PrincipalSessions

DSN = os.getenv("TEST_AGENT_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DSN, reason="disposable PostgreSQL test database not configured"
)


@pytest.fixture(scope="module")
def database():
    with psycopg.connect(DSN, autocommit=True) as conn:
        if conn.info.dbname != "agent_test":
            pytest.fail("TEST_AGENT_DATABASE_URL must select the disposable agent_test database")
        conn.execute("""
            DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='flamoris_ai_owner') THEN
                CREATE ROLE flamoris_ai_owner NOLOGIN;
            END IF;
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='flamoris_ai_app') THEN
                CREATE ROLE flamoris_ai_app NOLOGIN;
            END IF;
            END $$;
        """)
        conn.execute("GRANT CREATE ON DATABASE agent_test TO flamoris_ai_owner")
        root = Path(__file__).resolve().parents[1]
        conn.execute((root / "db/01_schema.sql").read_text())
        migration = (root / "db/migrations/002_principal_sessions.sql").read_text()
        conn.execute(migration)
        conn.execute(migration)  # Repeat application must preserve existing grants/bindings.
    return DSN


@pytest.fixture
def authorization(database):
    with psycopg.connect(database, autocommit=True) as conn:
        conn.execute(
            "TRUNCATE chat.principal_sessions, core.principal_grants, "
            "core.agent_projects, core.humans, core.agents, core.projects CASCADE"
        )
        project = conn.execute(
            "INSERT INTO core.projects(project_key, slug, name) "
            "VALUES ('project', 'project', 'Project') RETURNING id"
        ).fetchone()[0]
        agent = conn.execute(
            "INSERT INTO core.agents(agent_key, display_name) "
            "VALUES ('helper', 'Helper') RETURNING id"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO core.agent_projects(agent_id, project_id) VALUES (%s, %s)",
            (agent, project),
        )
        humans = [
            conn.execute(
                "INSERT INTO core.humans(human_key, display_name) VALUES (%s, %s) RETURNING id",
                (name, name),
            ).fetchone()[0]
            for name in ("first", "second")
        ]
        for human in humans:
            conn.execute(
                "INSERT INTO core.principal_grants(delegator_key, human_id, agent_id, project_id) "
                "VALUES ('backend', %s, %s, %s)",
                (human, agent, project),
            )

    def connection():
        conn = psycopg.connect(database, autocommit=True)
        conn.execute("SET ROLE flamoris_ai_app")
        return conn

    return PrincipalSessions(connection), database, (*humans, agent, project)


def test_two_principals_restart_and_other_delegator_denial(authorization):
    sessions, _, _ = authorization
    first = sessions.open("backend", PrincipalKeys("first", "helper", "project"))
    second = sessions.open("backend", PrincipalKeys("second", "helper", "project"))
    assert first.human_id != second.human_id and first.session_id != second.session_id
    restarted = PrincipalSessions(sessions.connection_factory)
    assert restarted.require("backend", first.session_id) == first
    assert restarted.require("backend", second.session_id) == second
    with pytest.raises(IntelligenceError, match="principal_unavailable"):
        restarted.require("other-backend", first.session_id)


def test_unknown_or_forbidden_combination_has_no_session_write(authorization):
    sessions, dsn, _ = authorization
    for keys in (
        PrincipalKeys("missing", "helper", "project"),
        PrincipalKeys("first", "missing", "project"),
        PrincipalKeys("first", "helper", "missing"),
    ):
        with pytest.raises(IntelligenceError, match="principal_unavailable"):
            sessions.open("backend", keys)
    with pytest.raises(IntelligenceError, match="principal_unavailable"):
        sessions.open("other-backend", PrincipalKeys("first", "helper", "project"))
    with psycopg.connect(dsn) as conn:
        assert conn.execute("SELECT count(*) FROM chat.principal_sessions").fetchone() == (0,)


@pytest.mark.parametrize(
    "revoke",
    [
        "UPDATE core.principal_grants SET enabled=FALSE",
        "UPDATE core.humans SET enabled=FALSE",
        "UPDATE core.agents SET enabled=FALSE",
        "UPDATE core.projects SET status='closed'",
        "DELETE FROM core.agent_projects",
        "UPDATE chat.principal_sessions SET revoked_at=clock_timestamp()",
    ],
)
def test_each_membership_or_session_revocation_blocks_continuation(authorization, revoke):
    sessions, dsn, _ = authorization
    bound = sessions.open("backend", PrincipalKeys("first", "helper", "project"))
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(revoke)
    with pytest.raises(IntelligenceError, match="principal_unavailable"):
        sessions.require("backend", bound.session_id)


def test_expired_binding_is_unavailable_and_existing_binding_cannot_change(authorization):
    sessions, dsn, (first, second, agent, project) = authorization
    bound = sessions.open("backend", PrincipalKeys("first", "helper", "project"))
    with psycopg.connect(dsn, autocommit=True) as conn:
        for field, value in (
            ("human_id", second),
            ("agent_id", uuid4()),
            ("project_id", uuid4()),
            ("delegator_key", "other"),
        ):
            with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
                conn.execute(
                    f"UPDATE chat.principal_sessions SET {field}=%s WHERE id=%s",
                    (value, bound.session_id),
                )
        expired = uuid4()
        conn.execute(
            "INSERT INTO chat.principal_sessions "
            "(id, delegator_key, human_id, agent_id, project_id, created_at, expires_at) "
            "VALUES (%s, 'backend', %s, %s, %s, now()-interval '1 hour', "
            "now()-interval '45 minutes')",
            (expired, first, agent, project),
        )
    assert sessions.require("backend", bound.session_id) == bound
    with pytest.raises(IntelligenceError, match="principal_unavailable"):
        sessions.require("backend", expired)


def test_runtime_cannot_create_or_reenable_its_own_grants(authorization):
    sessions, _, (first, _, agent, project) = authorization
    with sessions.connection_factory() as conn:
        for sql, params in (
            (
                "INSERT INTO core.principal_grants VALUES ('other', %s, %s, %s, TRUE)",
                (first, agent, project),
            ),
            ("UPDATE core.principal_grants SET enabled=TRUE", ()),
            ("DELETE FROM core.principal_grants", ()),
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql, params)


def test_capacity_refuses_new_binding_without_evicting_history(authorization):
    sessions, dsn, _ = authorization
    keys = PrincipalKeys("first", "helper", "project")
    first = sessions.open("backend", keys)
    for _ in range(31):
        sessions.open("backend", keys)
    with pytest.raises(IntelligenceError, match="principal_capacity"):
        sessions.open("backend", keys)
    assert sessions.require("backend", first.session_id) == first
    with psycopg.connect(dsn) as conn:
        assert conn.execute("SELECT count(*) FROM chat.principal_sessions").fetchone() == (32,)
