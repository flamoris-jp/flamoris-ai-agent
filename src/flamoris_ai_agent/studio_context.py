"""Versioned metadata-only Image context; identifiers grant no retrieval authority."""

import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContextModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)


class ImageDraft(ContextModel):
    positive_prompt: str = Field(default="", max_length=16384)
    negative_prompt: str = Field(default="", max_length=16384)
    width: int | None = Field(default=None, ge=64, le=4096, multiple_of=8)
    height: int | None = Field(default=None, ge=64, le=4096, multiple_of=8)
    steps: int | None = Field(default=None, ge=1, le=150)
    cfg: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    denoise: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    seed: int | None = Field(default=None, ge=0, le=2**64 - 1)


class WorkflowContext(ContextModel):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    version: int = Field(ge=1, le=100000)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    profile: Literal["image"] = "image"
    profile_revision: Literal[1] = 1

    @field_validator("profile_revision", mode="before")
    @classmethod
    def exact_revision(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("unsupported_profile_revision")
        return value


class AssetContext(ContextModel):
    id: str
    display_name: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    media_kind: Literal["image"] = "image"
    mime_type: Literal["image/png", "image/jpeg", "image/webp"]
    size_bytes: int | None = Field(default=None, ge=0, le=1024**3)

    @field_validator("id")
    @classmethod
    def uuid_string(cls, value):
        return str(UUID(value))


class StudioContext(ContextModel):
    revision: Literal[1]
    category: Literal["image"]
    operation: Literal["image.generate"]
    product_context_id: str
    draft_revision: int = Field(ge=1, le=2**31 - 1)
    draft: ImageDraft
    workflow: WorkflowContext | None = None
    assets: list[AssetContext] = Field(default_factory=list, max_length=8)

    @field_validator("revision", mode="before")
    @classmethod
    def exact_revision(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("unsupported_context_revision")
        return value

    @field_validator("product_context_id")
    @classmethod
    def uuid_string(cls, value):
        return str(UUID(value))

    def serialized(self):
        return json.dumps(
            {"kind": "untrusted_studio_context", "context": self.model_dump()},
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @model_validator(mode="after")
    def bounded(self):
        if len(self.serialized().encode()) > 16384:
            raise ValueError("studio_context_too_large")
        if len({asset.id for asset in self.assets}) != len(self.assets):
            raise ValueError("duplicate_asset_context")
        return self
