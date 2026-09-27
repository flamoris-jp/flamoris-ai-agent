"""Deployment configuration and bounded, ordered Agent context resources."""

import os
import re
import tomllib
from importlib.resources import files
from pathlib import Path

from dotenv import load_dotenv


class AgentContextError(ValueError):
    """Invalid or missing deployment-owned Agent context."""


def agent_home() -> Path | None:
    configured = os.getenv("FLAMORIS_AGENT_HOME")
    if configured:
        home = Path(configured).expanduser()
        if not home.is_absolute():
            raise ValueError("FLAMORIS_AGENT_HOME must be an absolute directory")
        if not home.is_dir():
            raise ValueError("FLAMORIS_AGENT_HOME must exist")
        return home
    source = Path(__file__).resolve().parents[2]
    if (source / "pyproject.toml").is_file() and (source / "agents").is_dir():
        return source
    return None


AGENT_HOME = agent_home()
if AGENT_HOME is not None:
    load_dotenv(AGENT_HOME / ".env")


def _read_bounded(resource, limit: int, label: str) -> str:
    try:
        with resource.open("rb") as stream:
            data = stream.read(limit + 1)
    except OSError as exc:
        raise AgentContextError(f"Missing or unreadable Agent {label}: {resource}") from exc
    if len(data) > limit:
        raise AgentContextError(f"Agent {label} exceeds {limit} bytes: {resource}")
    try:
        return data.decode("utf-8")
    except UnicodeError as exc:
        raise AgentContextError(f"Agent {label} must be UTF-8: {resource}") from exc


def load_agent_context() -> list[dict[str, str]]:
    """Load a manifest's sections in order; never fall back to another Agent."""
    key = os.getenv("FLAMORIS_AGENT_KEY", "example-agent")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
        raise AgentContextError("FLAMORIS_AGENT_KEY must be a simple agent name")
    directory = (
        AGENT_HOME / "agents" / key
        if AGENT_HOME is not None
        else files("flamoris_ai_agent").joinpath("agents", key)
    )
    manifest = directory.joinpath("agent.toml")
    if isinstance(directory, Path) and AGENT_HOME is not None:
        if not directory.resolve().is_relative_to((AGENT_HOME / "agents").resolve()):
            raise AgentContextError("Agent directory escapes selected home")
        if not manifest.resolve().is_relative_to(directory.resolve()):
            raise AgentContextError("Agent manifest escapes selected directory")
    try:
        raw = tomllib.loads(_read_bounded(manifest, 16384, "manifest"))
    except tomllib.TOMLDecodeError as exc:
        raise AgentContextError(f"Invalid Agent manifest {manifest}: {exc}") from exc
    if set(raw) != {"version", "context"} or type(raw["version"]) is not int or raw["version"] != 1:
        raise AgentContextError(f"Agent manifest {manifest} requires version = 1 and context")
    entries = raw["context"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 16:
        raise AgentContextError(f"Agent manifest {manifest} requires 1..16 context sections")
    sections = []
    seen_files, seen_titles = set(), set()
    total_bytes = 0
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"title", "file"}:
            raise AgentContextError(f"Agent manifest {manifest} needs title and file per section")
        title, name = entry["title"], entry["file"]
        if (
            not isinstance(title, str)
            or not title.strip()
            or len(title) > 80
            or any(ord(c) < 32 or ord(c) == 127 for c in title)
            or not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.md", name)
            or name in seen_files
            or title in seen_titles
        ):
            raise AgentContextError(f"Invalid or duplicate Agent context entry in {manifest}")
        resource = directory.joinpath(name)
        if isinstance(directory, Path) and not resource.resolve().is_relative_to(
            directory.resolve()
        ):
            raise AgentContextError(f"Agent context file escapes selected directory: {name}")
        content = _read_bounded(resource, 32768, "context file")
        if not content.strip():
            raise AgentContextError(f"Agent context file must not be empty: {name}")
        total_bytes += len(content.encode("utf-8"))
        if total_bytes > 32768:
            raise AgentContextError("Agent context exceeds 32768 bytes in total")
        sections.append({"title": title, "file": name, "content": content})
        seen_files.add(name)
        seen_titles.add(title)
    return sections
