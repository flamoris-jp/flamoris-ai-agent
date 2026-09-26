import os
import platform
import sys
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from flamoris_ai_agent.config import AGENT_HOME


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"環境変数 {name} がありません。"
            f"環境設定または {AGENT_HOME} の .env を確認してください。"
        )
    return value


def get_connection():
    return psycopg.connect(
        host=_required_env("PGHOST"),
        port=int(_required_env("PGPORT")),
        dbname=_required_env("PGDATABASE"),
        user=_required_env("PGUSER"),
        password=_required_env("PGPASSWORD"),
        connect_timeout=5,
        options="-c statement_timeout=5000 -c lock_timeout=2000",
        autocommit=True,
    )


def _lookup_one(conn, sql: str, value: str, label: str):
    row = conn.execute(sql, (value,)).fetchone()
    if not row:
        raise RuntimeError(
            f"{label} '{value}' がDBに登録されていません。"
            " db/02_seed_umeko.sql を実行したか確認してください。"
        )
    return row[0]


def load_runtime_refs(conn) -> dict[str, Any]:
    human_key = _required_env("FLAMORIS_HUMAN_KEY")
    agent_key = _required_env("FLAMORIS_AGENT_KEY")
    project_key = _required_env("FLAMORIS_PROJECT_KEY")
    host_key = _required_env("FLAMORIS_HOST_KEY")
    application_key = _required_env("FLAMORIS_APPLICATION_KEY")
    model_key = _required_env("FLAMORIS_MODEL_KEY")

    return {
        "human_id": _lookup_one(
            conn, "SELECT id FROM core.humans WHERE human_key = %s AND enabled", human_key, "Human"
        ),
        "agent_id": _lookup_one(
            conn, "SELECT id FROM core.agents WHERE agent_key = %s AND enabled", agent_key, "Agent"
        ),
        "project_id": _lookup_one(
            conn, "SELECT id FROM core.projects WHERE project_key = %s", project_key, "Project"
        ),
        "host_id": _lookup_one(
            conn, "SELECT id FROM runtime.hosts WHERE host_key = %s AND enabled", host_key, "Host"
        ),
        "application_id": _lookup_one(
            conn,
            "SELECT id FROM runtime.applications WHERE application_key = %s AND enabled",
            application_key,
            "Application",
        ),
        "model_id": _lookup_one(
            conn,
            "SELECT id FROM runtime.models WHERE model_key = %s AND enabled",
            model_key,
            "Model",
        ),
    }


def validate_model_ref(conn, model_id, served_model: str, provider: str = "llama.cpp"):
    """Validate immutable runtime provenance without choosing a provider."""
    row = conn.execute(
        "SELECT provider, model_name FROM runtime.models WHERE id = %s",
        (model_id,),
    ).fetchone()
    if row != (provider, served_model):
        raise RuntimeError(
            "Model identity mismatch; run register_runtime with a new model key first"
        )


def get_previous_conversation(conn, agent_id, project_id, message_limit: int = 12):
    conversation = conn.execute(
        """
        SELECT c.id, c.created_at, c.ended_at
        FROM chat.conversations AS c
        WHERE c.primary_agent_id = %s
          AND c.project_id = %s
        ORDER BY c.created_at DESC
        LIMIT 1
        """,
        (agent_id, project_id),
    ).fetchone()

    if not conversation:
        return None

    rows = conn.execute(
        """
        SELECT
            m.role,
            COALESCE(p.display_name, m.role) AS sender,
            m.content,
            m.created_at
        FROM chat.messages AS m
        LEFT JOIN chat.participants AS p
          ON p.id = m.sender_participant_id
        WHERE m.conversation_id = %s
        ORDER BY m.ordinal DESC
        LIMIT %s
        """,
        (conversation[0], message_limit),
    ).fetchall()

    rows.reverse()
    return {
        "conversation_id": conversation[0],
        "created_at": conversation[1],
        "ended_at": conversation[2],
        "messages": [
            {"role": r[0], "sender": r[1], "content": r[2], "created_at": r[3]} for r in rows
        ],
    }


def start_instance(conn, refs: dict[str, Any]):
    metadata = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "executable": sys.executable,
    }
    return conn.execute(
        """
        INSERT INTO runtime.instances (
            host_id, application_id, agent_id, model_id,
            instance_label, process_id, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            refs["host_id"],
            refs["application_id"],
            refs["agent_id"],
            refs["model_id"],
            os.getenv("FLAMORIS_INSTANCE_LABEL", "console"),
            os.getpid(),
            Jsonb(metadata),
        ),
    ).fetchone()[0]


def start_conversation(conn, refs, instance_id, system_prompt, system_context):
    with conn.transaction():
        conversation_id = conn.execute(
            """
            INSERT INTO chat.conversations (
                project_id, primary_agent_id, system_prompt, system_context, metadata
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                refs["project_id"],
                refs["agent_id"],
                system_prompt,
                Jsonb(system_context),
                Jsonb({"client": "umeko-chat"}),
            ),
        ).fetchone()[0]

        human_participant_id = conn.execute(
            """
            INSERT INTO chat.participants (conversation_id, human_id, display_name)
            SELECT %s, id, display_name FROM core.humans WHERE id = %s
            RETURNING id
            """,
            (conversation_id, refs["human_id"]),
        ).fetchone()[0]

        agent_participant_id = conn.execute(
            """
            INSERT INTO chat.participants (conversation_id, agent_id, display_name)
            SELECT %s, id, display_name FROM core.agents WHERE id = %s
            RETURNING id
            """,
            (conversation_id, refs["agent_id"]),
        ).fetchone()[0]

        conversation_session_id = conn.execute(
            """
            INSERT INTO chat.conversation_sessions (conversation_id, instance_id)
            VALUES (%s, %s)
            RETURNING id
            """,
            (conversation_id, instance_id),
        ).fetchone()[0]

    return {
        "conversation_id": conversation_id,
        "human_participant_id": human_participant_id,
        "agent_participant_id": agent_participant_id,
        "conversation_session_id": conversation_session_id,
    }


def save_message(
    conn, conversation_id, sender_participant_id, role, content, origin_instance_id, metadata=None
):
    return conn.execute(
        """
        INSERT INTO chat.messages (
            conversation_id, sender_participant_id, role,
            content, origin_instance_id, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, ordinal
        """,
        (
            conversation_id,
            sender_participant_id,
            role,
            content,
            origin_instance_id,
            Jsonb(metadata or {}),
        ),
    ).fetchone()


def close_runtime(conn, conversation_id, conversation_session_id, instance_id):
    with conn.transaction():
        conn.execute(
            "UPDATE chat.conversation_sessions "
            "SET left_at = COALESCE(left_at, now()) WHERE id = %s",
            (conversation_session_id,),
        )
        conn.execute(
            """
            UPDATE chat.conversations
            SET ended_at = COALESCE(ended_at, now()),
                status = CASE WHEN status = 'open' THEN 'closed' ELSE status END
            WHERE id = %s
            """,
            (conversation_id,),
        )
        conn.execute(
            "UPDATE runtime.instances SET ended_at = COALESCE(ended_at, now()) WHERE id = %s",
            (instance_id,),
        )


def close_instance(conn, instance_id):
    """Close a started instance if conversation creation failed."""
    conn.execute(
        "UPDATE runtime.instances SET ended_at = COALESCE(ended_at, now()) WHERE id = %s",
        (instance_id,),
    )
