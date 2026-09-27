"""Run with a wheel-only interpreter outside the source checkout; no live services."""

import os
import subprocess
import sys
import tempfile
from importlib.metadata import distribution
from pathlib import Path

import flamoris_ai_agent
from flamoris_ai_agent import db, intelligence, prompts, register_runtime, verify_db

assert "site-packages" in Path(flamoris_ai_agent.__file__).parts
assert all(section["content"] for section in prompts.load_system_context())
assert db.get_connection and intelligence.IntelligenceClient
assert register_runtime.main and verify_db.main
entries = {e.name: e for e in distribution("flamoris-ai-agent").entry_points}
for name in ("flamoris-agent-chat", "flamoris-agent-register-runtime", "flamoris-agent-verify-db"):
    assert callable(entries[name].load())
assert callable(entries["flamoris-agent-mcp"].load())
with tempfile.TemporaryDirectory() as home:
    agent = Path(home, "agents", "custom")
    agent.mkdir(parents=True)
    (agent / "agent.toml").write_text(
        'version = 1\n[[context]]\ntitle = "Identity"\nfile = "identity.md"\n'
    )
    (agent / "identity.md").write_text("Private deployment example")
    env = {**os.environ, "FLAMORIS_AGENT_HOME": home, "FLAMORIS_AGENT_KEY": "custom"}
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from flamoris_ai_agent.config import load_agent_context; "
            "assert load_agent_context()[0]['content'] == 'Private deployment example'",
        ],
        env=env,
        check=True,
    )
    env["FLAMORIS_AGENT_KEY"] = "example-agent"
    missing = subprocess.run(
        [
            sys.executable,
            "-c",
            "from flamoris_ai_agent.config import load_agent_context; load_agent_context()",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing.returncode != 0 and "agent.toml" in missing.stderr
print("Installed package, entry points, and manifest context resources: OK")
