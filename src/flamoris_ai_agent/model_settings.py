"""Explicit allowlisted model grants and immutable principal session selection."""

import hashlib
import json
import os

from flamoris_update_core.admission import guarded
from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

from .execution import IntelligenceError
from .execution_target import ApprovedTarget


class ModelOption(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    id: StrictStr = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    display_name: StrictStr = Field(min_length=1, max_length=128)
    model_key: StrictStr = Field(min_length=1, max_length=256)
    target: ApprovedTarget

    @model_validator(mode="after")
    def mapping(self):
        if self.id != self.target.public_model_id:
            raise ValueError("model_identity_mismatch")
        if (self.target.provider_id == "openai") != (self.target.data_flow == "remote_authorized"):
            raise ValueError("invalid_data_flow")
        if self.target.provider_id not in {"openai", "llamacpp"}:
            raise ValueError("unsupported_provider")
        if (
            self.target.db_provider
            != {"openai": "openai", "llamacpp": "llama.cpp"}[self.target.provider_id]
        ):
            raise ValueError("invalid_db_provider")
        return self

    @property
    def digest(self):
        # Endpoint/registry changes invalidate sessions; credentials are absent.
        payload = [
            "direct-execution-v1",
            self.model_dump(),
            os.getenv("INTELLIGENCE_BASE_URL", "http://127.0.0.1:8081"),
            {
                name: os.getenv("FLAMORIS_INTELLIGENCE_" + name.upper(), "")
                for name in (
                    "openai_input_usd_per_million",
                    "openai_output_usd_per_million",
                    "openai_max_request_usd",
                )
            },
        ]
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def registry():
    try:
        raw = os.environ["AGENT_INTELLIGENCE_TARGETS"]
        if len(raw.encode()) > 65536:
            raise ValueError()
        entries = json.loads(raw)
        if type(entries) is not list or not 1 <= len(entries) <= 16:
            raise ValueError()
        options = [ModelOption.model_validate(e) for e in entries]
        if len({o.id for o in options}) != len(options) or len(
            {o.model_key for o in options}
        ) != len(options):
            raise ValueError()
        return {o.id: o for o in options}
    except (ValueError, KeyError, TypeError):
        raise IntelligenceError("invalid_intelligence_configuration") from None


class ModelSettings:
    def __init__(self, principals):
        self.principals = principals

    @staticmethod
    def allowed_on(conn, binding, option):
        row = conn.execute(
            "SELECT m.id,g.allow_remote FROM runtime.models m JOIN core.model_grants g "
            "ON g.model_id=m.id AND g.enabled WHERE m.model_key=%s AND m.enabled "
            "AND m.provider=%s AND m.model_name=%s AND g.delegator_key=%s AND g.human_id=%s "
            "AND g.agent_id=%s AND g.project_id=%s",
            (
                option.model_key,
                option.target.db_provider,
                option.target.db_model_name,
                binding.delegator,
                binding.human_id,
                binding.agent_id,
                binding.project_id,
            ),
        ).fetchone()
        if row is None or option.target.data_flow == "remote_authorized" and not row[1]:
            raise IntelligenceError("model_forbidden")
        return row[0]

    def list(self, caller, keys):
        # Discovery validates grants without consuming a bounded principal session.
        from .principals import PrincipalBinding

        with self.principals.connection_factory() as conn:
            row = conn.execute(
                "SELECT h.id,a.id,p.id FROM core.humans h "
                "JOIN core.agents a ON a.agent_key=%s AND a.enabled "
                "JOIN core.projects p ON p.project_key=%s AND p.status='active' "
                "JOIN core.agent_projects ap ON ap.agent_id=a.id AND ap.project_id=p.id "
                "JOIN core.principal_grants g ON g.human_id=h.id AND g.agent_id=a.id "
                "AND g.project_id=p.id AND g.delegator_key=%s AND g.enabled "
                "WHERE h.human_key=%s AND h.enabled",
                (keys.agent, keys.project, caller, keys.human),
            ).fetchone()
            if not row:
                raise IntelligenceError("principal_unavailable")
            bound = PrincipalBinding(None, caller, keys, *row, None)
            values = []
            for option in registry().values():
                try:
                    self.allowed_on(conn, bound, option)
                except IntelligenceError:
                    continue
                values.append(
                    {
                        "id": option.id,
                        "display_name": option.display_name,
                        "data_flow": option.target.data_flow,
                    }
                )
            return {"models": values, "default_model_id": os.getenv("AGENT_DEFAULT_MODEL_ID")}

    def bind_on(self, conn, binding, model_id, remote_consent):
        option = registry().get(model_id or os.getenv("AGENT_DEFAULT_MODEL_ID"))
        if option is None:
            raise IntelligenceError("model_forbidden")
        model = self.allowed_on(conn, binding, option)
        if option.target.data_flow == "remote_authorized" and remote_consent is not True:
            raise IntelligenceError("remote_consent_required")
        conn.execute(
            "INSERT INTO chat.principal_options "
            "(session_id,public_model_id,target_digest,model_id,remote_consent,data_flow) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (
                binding.session_id,
                option.id,
                option.digest,
                model,
                remote_consent,
                option.target.data_flow,
            ),
        )

    def require(self, binding):
        with self.principals.connection_factory() as conn:
            current = self.principals.require_on(conn, binding.delegator, binding.session_id)
            if current != binding:
                raise IntelligenceError("principal_unavailable")
            row = conn.execute(
                "SELECT public_model_id,target_digest,model_id,remote_consent,data_flow "
                "FROM chat.principal_options WHERE session_id=%s",
                (binding.session_id,),
            ).fetchone()
            option = registry().get(row[0]) if row else None
            if option is None or option.digest != row[1] or option.target.data_flow != row[4]:
                raise IntelligenceError("model_selection_changed")
            if self.allowed_on(conn, binding, option) != row[2]:
                raise IntelligenceError("model_selection_changed")
            if option.target.data_flow == "remote_authorized" and row[3] is not True:
                raise IntelligenceError("remote_consent_required")
            return option


@guarded()
def main():
    """Explicit operator registration of model identities; no provider calls/grants."""
    from . import db

    with db.get_connection() as conn, conn.transaction():
        for option in registry().values():
            conn.execute(
                "INSERT INTO runtime.models(model_key,provider,model_name) VALUES (%s,%s,%s) "
                "ON CONFLICT(model_key) DO NOTHING",
                (option.model_key, option.target.db_provider, option.target.db_model_name),
            )
            row = conn.execute(
                "SELECT provider,model_name,enabled FROM runtime.models WHERE model_key=%s",
                (option.model_key,),
            ).fetchone()
            if row != (option.target.db_provider, option.target.db_model_name, True):
                raise IntelligenceError("model_selection_changed")
    print(
        "Registered configured model identities; existing identities preserved; no grants created"
    )
