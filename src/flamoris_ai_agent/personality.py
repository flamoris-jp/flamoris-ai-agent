"""Agent-owned immutable personality revisions and explicit editor grants."""

import hashlib
import json
import os
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator

from . import db
from .execution import IntelligenceError


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    title: StrictStr = Field(min_length=1, max_length=80)
    content: StrictStr = Field(min_length=1, max_length=32768)


class PersonalityBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    display_name: StrictStr = Field(min_length=1, max_length=128)
    sections: list[Section] = Field(min_length=1, max_length=16)

    @field_validator("display_name")
    @classmethod
    def name(cls, value):
        if not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("invalid_name")
        return value

    @field_validator("sections")
    @classmethod
    def valid_sections(cls, value):
        if len({s.title for s in value}) != len(value):
            raise ValueError("duplicate_section")
        size = 0
        for section in value:
            if not section.title.strip() or any(
                ord(c) < 32 or ord(c) == 127 for c in section.title
            ):
                raise ValueError("invalid_title")
            if not section.content.strip() or any(
                ord(c) < 32 and c not in "\n\r\t" for c in section.content
            ):
                raise ValueError("invalid_content")
            size += len(section.content.encode("utf-8"))
        if size > 32768:
            raise ValueError("context_too_large")
        return value


class PersonalityRead(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    session_id: StrictStr
    before_revision: StrictInt | None = Field(default=None, ge=1, le=257)

    @field_validator("session_id")
    @classmethod
    def uuid(cls, value):
        return str(UUID(value))


class PersonalitySave(PersonalityBody):
    session_id: StrictStr
    request_id: StrictStr
    expected_revision: StrictInt = Field(ge=1, le=256)

    @field_validator("session_id", "request_id")
    @classmethod
    def uuid(cls, value):
        if str(UUID(value)) != value:
            raise ValueError("invalid_uuid")
        return value


class ContextSnapshot(list):
    def __init__(self, sections, revision):
        super().__init__(sections)
        self.revision = revision


def context_source():
    source = os.getenv("AGENT_CONTEXT_SOURCE", "file")
    if source not in {"file", "db"}:
        raise IntelligenceError("invalid_agent_context")
    return source


def load_context(agent_key=None):
    if context_source() == "file":
        from .config import load_agent_context

        return ContextSnapshot(load_agent_context(agent_key), None)
    key = agent_key or os.getenv("FLAMORIS_AGENT_KEY", "example-agent")
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT v.sections, v.revision, v.display_name FROM core.agents a "
            "JOIN core.agent_personalities p ON p.agent_id=a.id "
            "JOIN core.personality_versions v ON v.agent_id=p.agent_id "
            "AND v.revision=p.revision "
            "WHERE a.agent_key=%s AND a.enabled",
            (key,),
        ).fetchone()
        if row is None:
            raise IntelligenceError("invalid_agent_context")
        body = PersonalityBody.model_validate({"display_name": row[2], "sections": row[0]})
        return ContextSnapshot([s.model_dump() for s in body.sections], row[1])


class PersonalityStore:
    def __init__(self, principals):
        self.principals = principals

    def authorize(self, conn, caller, session_id, edit=False):
        binding = self.principals.require_on(conn, caller, session_id, lock=edit)
        row = conn.execute(
            "SELECT can_read, can_edit FROM core.personality_grants "
            "WHERE delegator_key=%s AND human_id=%s AND agent_id=%s AND enabled ",
            (caller, binding.human_id, binding.agent_id),
        ).fetchone()
        if row is None or not row[1 if edit else 0]:
            raise IntelligenceError("personality_forbidden")
        return binding, row[1]

    @staticmethod
    def public(row, can_edit):
        body = PersonalityBody.model_validate({"display_name": row[1], "sections": row[2]})
        return {
            "revision": row[0],
            **body.model_dump(),
            "can_edit": can_edit and context_source() == "db",
            "updated_at": row[3].isoformat(),
            "scope": "shared_agent",
        }

    def get(self, caller, request):
        with self.principals.connection_factory() as conn:
            bound, can_edit = self.authorize(conn, caller, request.session_id)
            row = conn.execute(
                "SELECT v.revision,v.display_name,v.sections,v.created_at "
                "FROM core.agent_personalities p "
                "JOIN core.personality_versions v ON v.agent_id=p.agent_id "
                "AND v.revision=p.revision "
                "WHERE p.agent_id=%s",
                (bound.agent_id,),
            ).fetchone()
            if row is None:
                raise IntelligenceError("personality_unavailable")
            return self.public(row, can_edit)

    def history(self, caller, request):
        with self.principals.connection_factory() as conn:
            bound, can_edit = self.authorize(conn, caller, request.session_id)
            rows = conn.execute(
                "SELECT revision,display_name,sections,created_at FROM core.personality_versions "
                "WHERE agent_id=%s AND revision < %s ORDER BY revision DESC LIMIT 1",
                (bound.agent_id, request.before_revision or 257),
            ).fetchall()
            return {
                "versions": [self.public(r, can_edit) for r in rows],
                "before_revision": rows[-1][0] if rows and rows[-1][0] > 1 else None,
            }

    def save(self, caller, request):
        if context_source() != "db":
            raise IntelligenceError("personality_source_disabled")
        body = PersonalityBody(display_name=request.display_name, sections=request.sections)
        stamp = hashlib.sha256(
            json.dumps(
                {"expected_revision": request.expected_revision, **body.model_dump()},
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest()
        with self.principals.connection_factory() as conn, conn.transaction():
            bound, _ = self.authorize(conn, caller, request.session_id, edit=True)
            head = conn.execute(
                "SELECT revision FROM core.agent_personalities WHERE agent_id=%s FOR UPDATE",
                (bound.agent_id,),
            ).fetchone()
            if head is None:
                raise IntelligenceError("personality_unavailable")
            self.authorize(conn, caller, request.session_id, edit=True)
            old = conn.execute(
                "SELECT revision,request_digest,updated_by,delegator_key "
                "FROM core.personality_versions "
                "WHERE agent_id=%s AND request_id=%s",
                (bound.agent_id, request.request_id),
            ).fetchone()
            if old:
                if old[1:] != (stamp, bound.human_id, caller):
                    raise IntelligenceError("update_identity_mismatch")
                return {"revision": old[0], "duplicate": True}
            if head[0] != request.expected_revision:
                raise IntelligenceError("revision_conflict")
            if head[0] >= 256:
                raise IntelligenceError("personality_capacity")
            revision = head[0] + 1
            conn.execute(
                "INSERT INTO core.personality_versions "
                "(agent_id,revision,display_name,sections,request_id,request_digest,"
                "updated_by,delegator_key) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    bound.agent_id,
                    revision,
                    body.display_name,
                    Jsonb([s.model_dump() for s in body.sections]),
                    request.request_id,
                    stamp,
                    bound.human_id,
                    caller,
                ),
            )
            conn.execute(
                "UPDATE core.agent_personalities SET revision=%s WHERE agent_id=%s",
                (revision, bound.agent_id),
            )
            return {"revision": revision, "duplicate": False}


def import_personality(conn, agent_key, display_name, sections):
    body = PersonalityBody.model_validate(
        {
            "display_name": display_name,
            "sections": [{"title": s["title"], "content": s["content"]} for s in sections],
        }
    )
    with conn.transaction():
        agent = conn.execute(
            "SELECT id FROM core.agents WHERE agent_key=%s AND enabled FOR UPDATE", (agent_key,)
        ).fetchone()
        if not agent:
            raise IntelligenceError("personality_unavailable")
        if conn.execute(
            "SELECT 1 FROM core.agent_personalities WHERE agent_id=%s", (agent[0],)
        ).fetchone():
            raise IntelligenceError("revision_conflict")
        payload = body.model_dump()
        conn.execute(
            "INSERT INTO core.personality_versions "
            "(agent_id,revision,display_name,sections,request_id,request_digest,delegator_key) "
            "VALUES (%s,1,%s,%s,%s,%s,'operator-import')",
            (
                agent[0],
                body.display_name,
                Jsonb(payload["sections"]),
                uuid4(),
                hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            ),
        )
        conn.execute(
            "INSERT INTO core.agent_personalities(agent_id,revision) VALUES (%s,1)", (agent[0],)
        )
    return payload


def main():
    import argparse

    from .config import load_agent_context

    parser = argparse.ArgumentParser(description="Explicit validated file-to-DB personality import")
    parser.add_argument("--agent", required=True)
    parser.add_argument("--display-name", required=True)
    args = parser.parse_args()
    sections = load_agent_context(args.agent)
    with db.get_connection() as conn:
        imported = import_personality(conn, args.agent, args.display_name, sections)
        row = conn.execute(
            "SELECT v.sections FROM core.agents a JOIN core.personality_versions v "
            "ON v.agent_id=a.id AND v.revision=1 WHERE a.agent_key=%s",
            (args.agent,),
        ).fetchone()
        if row[0] != imported["sections"]:
            raise RuntimeError("import verification failed")
    print("Imported and verified revision 1; original files retained")
