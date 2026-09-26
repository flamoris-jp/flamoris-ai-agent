"""Local configuration and packaged personality resources, independent of cwd."""

import os
import re
from importlib.resources import files
from pathlib import Path

from dotenv import load_dotenv


def agent_home() -> Path | None:
    configured = os.getenv("FLAMORIS_AGENT_HOME")
    if configured:
        home = Path(configured).expanduser()
        if not home.is_absolute():
            raise ValueError("FLAMORIS_AGENT_HOME must be an absolute directory")
        if not home.is_dir():
            raise ValueError("FLAMORIS_AGENT_HOME must exist")
        return home
    # Preserve repository-root .env/personality editing for source installations.
    source = Path(__file__).resolve().parents[2]
    if (source / "pyproject.toml").is_file() and (source / "agents").is_dir():
        return source
    return None


AGENT_HOME = agent_home()
if AGENT_HOME is not None:
    load_dotenv(AGENT_HOME / ".env")


def load_agent_text(filename: str) -> str:
    key = os.getenv("FLAMORIS_AGENT_KEY", "umeko")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
        raise ValueError("FLAMORIS_AGENT_KEY must be a simple agent name")
    if filename not in {"personality.md", "flamoris.md", "characters.md"}:
        raise ValueError("Unknown Agent context file")
    if AGENT_HOME is not None:
        path = AGENT_HOME / "agents" / key / filename
        # A configured home is authoritative: never silently substitute identity.
        return path.read_text(encoding="utf-8")
    return files("flamoris_ai_agent").joinpath("agents", key, filename).read_text(encoding="utf-8")
