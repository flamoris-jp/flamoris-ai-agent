"""Persisted, bounded principal bindings for a separately authenticated delegator.

The delegator comes from transport authentication, never tool arguments. This
module grants no authority from a service credential or a session UUID alone.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from flamoris_ai_agent import db
from flamoris_ai_agent.execution import IntelligenceError

MAX_SESSIONS = 128
MAX_DELEGATOR_SESSIONS = 32
SESSION_SECONDS = 900


def key(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise IntelligenceError("principal_unavailable")
    return value


@dataclass(frozen=True)
class PrincipalKeys:
    human: str
    agent: str
    project: str

    def __post_init__(self):
        for value in (self.human, self.agent, self.project):
            key(value)


@dataclass(frozen=True)
class PrincipalBinding:
    session_id: UUID
    delegator: str
    keys: PrincipalKeys
    human_id: UUID
    agent_id: UUID
    project_id: UUID
    expires_at: datetime

    @property
    def ids(self):
        return {"human_id": self.human_id, "agent_id": self.agent_id, "project_id": self.project_id}


class PrincipalSessions:
    def __init__(self, connection_factory=None):
        self.connection_factory = connection_factory or db.get_connection

    def open(self, delegator, keys: PrincipalKeys):
        key(delegator)
        if not isinstance(keys, PrincipalKeys):
            raise IntelligenceError("principal_unavailable")
        with self.connection_factory() as conn, conn.transaction():
            # Serialize the bounded session namespace, not inference/GPU work.
            conn.execute("SELECT pg_advisory_xact_lock(1179402567, 18)")
            row = conn.execute(
                """
                SELECT h.id, a.id, p.id
                FROM core.humans h
                JOIN core.agents a ON a.agent_key = %s AND a.enabled
                JOIN core.projects p ON p.project_key = %s AND p.status = 'active'
                JOIN core.agent_projects ap ON ap.agent_id = a.id AND ap.project_id = p.id
                JOIN core.principal_grants g ON g.human_id = h.id AND g.agent_id = a.id
                  AND g.project_id = p.id AND g.delegator_key = %s AND g.enabled
                WHERE h.human_key = %s AND h.enabled
                """,
                (keys.agent, keys.project, delegator, keys.human),
            ).fetchone()
            if not row:
                raise IntelligenceError("principal_unavailable")
            # Expired/revoked rows are still retained and counted: no implicit GC
            # can delete a binding referenced by a conversation or uncertain ask.
            total, own = conn.execute(
                "SELECT count(*), count(*) FILTER (WHERE delegator_key = %s) "
                "FROM chat.principal_sessions",
                (delegator,),
            ).fetchone()
            if total >= MAX_SESSIONS or own >= MAX_DELEGATOR_SESSIONS:
                raise IntelligenceError("principal_capacity")
            session_id = uuid4()
            expires_at = conn.execute(
                """
                INSERT INTO chat.principal_sessions
                    (id, delegator_key, human_id, agent_id, project_id, created_at, expires_at)
                SELECT %s, %s, %s, %s, %s, stamp, stamp + %s * INTERVAL '1 second'
                FROM (SELECT clock_timestamp() AS stamp) t
                RETURNING expires_at
                """,
                (session_id, delegator, *row, SESSION_SECONDS),
            ).fetchone()[0]
            return PrincipalBinding(session_id, delegator, keys, *row, expires_at)

    def require(self, delegator, session_id):
        with self.connection_factory() as conn:
            return self.require_on(conn, delegator, session_id)

    @staticmethod
    def require_on(conn, delegator, session_id, *, lock=False):
        key(delegator)
        try:
            session_id = UUID(str(session_id))
        except (ValueError, TypeError, AttributeError):
            raise IntelligenceError("principal_unavailable") from None
        sql = """
            SELECT h.human_key, a.agent_key, p.project_key,
                   h.id, a.id, p.id, s.expires_at
            FROM chat.principal_sessions s
            JOIN core.humans h ON h.id = s.human_id AND h.enabled
            JOIN core.agents a ON a.id = s.agent_id AND a.enabled
            JOIN core.projects p ON p.id = s.project_id AND p.status = 'active'
            JOIN core.agent_projects ap ON ap.agent_id = a.id AND ap.project_id = p.id
            JOIN core.principal_grants g ON g.human_id = h.id AND g.agent_id = a.id
              AND g.project_id = p.id AND g.delegator_key = s.delegator_key AND g.enabled
            WHERE s.id = %s AND s.delegator_key = %s AND s.revoked_at IS NULL
              AND s.expires_at > clock_timestamp()
        """
        if lock:
            # Session revocation serializes with admission. Grant/membership
            # authorization linearizes at this read; admitted turns may drain
            # after later revocation and gain no new capabilities.
            sql += " FOR SHARE OF s"
        row = conn.execute(sql, (session_id, delegator)).fetchone()
        if not row:
            raise IntelligenceError("principal_unavailable")
        return PrincipalBinding(session_id, delegator, PrincipalKeys(*row[:3]), *row[3:])
