# Imported history (not active runtime)

These records are preserved migration evidence. Do not use them as current
installation instructions or rewrite their contents to describe today's code.
Normal lint, tests, and the installed wheel exclude this tree.

| Current location | Original imported location | Purpose |
|---|---|---|
| `ver_0/` | `history/ver_0/` | Earlier Umeko prototype and setup |
| `setup/` | `setup/` | Timestamped previous-conversation patch and its source |
| `ollama/umeko/Modelfile` | `agents/umeko/Modelfile` | Former active Ollama model definition |
| `ollama/umeko/variants/` | `agents/umeko/_archive/` | Archived Ollama model variants |
| `design/` | `docs/FLAMORIS_AI_構築設計記録_20260816.md` | Original architecture record |

Files were moved without changing their contents. Historical paths within them
describe the original layout. Active code is now `src/flamoris_ai_agent/`;
current setup is documented in `../docs/PHASE_0_RUNBOOK.md`.
