"""Exact-scope MCP persistence over the original schema; no latest lookup."""

import json
from uuid import NAMESPACE_URL, uuid5

import psycopg

from flamoris_ai_agent import db
from flamoris_ai_agent.execution import IntelligenceError
from flamoris_ai_agent.runtime import PostgresStore


def scope_id(refs):
    return str(
        uuid5(
            NAMESPACE_URL,
            "flamoris-agent:"
            + ":".join(str(refs[k]) for k in ("human_id", "agent_id", "project_id")),
        )
    )


class MCPStore(PostgresStore):
    def __init__(self, request):
        super().__init__()
        self.request = request

    def open(self, identity, load_previous=False):
        # Never call the console's unscoped previous-conversation query.
        super().open(identity, False)
        self.scope = scope_id(self.refs)
        self.request_conversation = uuid5(NAMESPACE_URL, self.scope + ":" + self.request.request_id)
        if self.conn.execute(
            "SELECT id FROM chat.conversations WHERE id = %s", (self.request_conversation,)
        ).fetchone():
            raise IntelligenceError("duplicate_request")
        parent = self.request.previous_conversation_id
        if parent is None:
            return None
        conversation = self.conn.execute(
            """
            SELECT c.id, c.created_at, c.ended_at
            FROM chat.conversations c
            WHERE c.id = %s AND c.project_id = %s AND c.primary_agent_id = %s
              AND c.status = 'closed' AND c.ended_at IS NOT NULL
              AND c.metadata->>'client' = 'agent-mcp'
              AND c.metadata->>'scope' = %s
              AND EXISTS (
                SELECT 1 FROM chat.participants p
                WHERE p.conversation_id = c.id AND p.human_id = %s)
              AND NOT EXISTS (
                SELECT 1 FROM chat.participants p WHERE p.conversation_id = c.id
                AND ((p.human_id IS NOT NULL AND p.human_id <> %s)
                  OR (p.agent_id IS NOT NULL AND p.agent_id <> %s)))
            """,
            (
                parent,
                self.refs["project_id"],
                self.refs["agent_id"],
                self.scope,
                self.refs["human_id"],
                self.refs["human_id"],
                self.refs["agent_id"],
            ),
        ).fetchone()
        if not conversation:
            raise IntelligenceError("conversation_unavailable")
        rows = self.conn.execute(
            """
            SELECT m.role, left(COALESCE(p.display_name, m.role), 513),
                   left(m.content, 65537), m.created_at
            FROM chat.messages m LEFT JOIN chat.participants p ON p.id=m.sender_participant_id
            WHERE m.conversation_id=%s ORDER BY m.ordinal DESC LIMIT 12
            """,
            (parent,),
        ).fetchall()
        messages = [
            {"role": r[0], "sender": r[1], "content": r[2], "created_at": r[3]}
            for r in reversed(rows)
        ]
        if any(len(m["sender"]) > 512 or len(m["content"].encode()) > 65536 for m in messages):
            raise IntelligenceError("input_too_large")
        if len(json.dumps(messages, default=str, ensure_ascii=False).encode()) > 65536:
            raise IntelligenceError("input_too_large")
        return {
            "conversation_id": conversation[0],
            "created_at": conversation[1],
            "ended_at": conversation[2],
            "messages": messages,
        }

    def start(self, policy, context):
        metadata = {
            "client": "agent-mcp",
            "scope": self.scope,
            "request_id": self.request.request_id,
            "previous_conversation_id": self.request.previous_conversation_id,
        }
        try:
            with self.conn.transaction():
                instance = db.start_instance(self.conn, self.refs)
                runtime = db.start_conversation(
                    self.conn,
                    self.refs,
                    instance,
                    policy,
                    context,
                    conversation_id=self.request_conversation,
                    metadata=metadata,
                )
        except psycopg.errors.UniqueViolation:
            raise IntelligenceError("duplicate_request") from None
        self.instance_id, self.runtime = instance, runtime
        return runtime["conversation_id"], instance
