"""Operator-approved execution identity and budgets, independent of transport."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ApprovedTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    public_model_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    provider_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    db_model_name: str = Field(min_length=1, max_length=512)
    db_provider: str = Field(min_length=1, max_length=128)
    capability_id: Literal["text.generate"] = "text.generate"
    max_input_bytes: int = Field(default=65536, ge=1, le=65536)
    context_tokens: int = Field(default=32768, ge=1024, le=1048576)
    max_output_tokens: int = Field(default=1024, ge=1, le=4096)
    timeout_seconds: float = Field(default=120, gt=0, le=120, allow_inf_nan=False)
    data_flow: str

    @field_validator("data_flow")
    @classmethod
    def data_policy(cls, value):
        if value not in {"local_only", "remote_authorized"}:
            raise ValueError("unsupported_data_flow")
        return value

    @model_validator(mode="after")
    def identity(self):
        if self.provider_id not in {"llamacpp", "openai"}:
            raise ValueError("unsupported_provider")
        if self.db_provider != {"llamacpp": "llama.cpp", "openai": "openai"}[self.provider_id]:
            raise ValueError("invalid_db_provider")
        if (self.provider_id == "openai") != (self.data_flow == "remote_authorized"):
            raise ValueError("invalid_data_flow")
        return self
