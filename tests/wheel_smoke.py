"""Run with a wheel-only interpreter outside the source checkout; no live services."""

from importlib.metadata import distribution
from pathlib import Path

import flamoris_ai_agent
from flamoris_ai_agent import db, intelligence, prompts, register_runtime, verify_db

assert "site-packages" in Path(flamoris_ai_agent.__file__).parts
assert all(prompts.load_system_context().values())
assert db.get_connection and intelligence.IntelligenceClient
assert register_runtime.main and verify_db.main
entries = {e.name: e for e in distribution("flamoris-ai-agent").entry_points}
for name in ("flamoris-agent-chat", "flamoris-agent-register-runtime", "flamoris-agent-verify-db"):
    assert callable(entries[name].load())
assert callable(entries["flamoris-agent-mcp"].load())
print("Installed package, entry points, and personality resources: OK")
