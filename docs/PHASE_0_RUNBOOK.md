# Phase 0: wake Umeko on GPT-OSS

Run the console app on LIME, where the llama.cpp endpoint is reachable on
`127.0.0.1:8081`. The imported database schema and Umeko agent key stay intact.
The model and host are separate runtime identities.

## Preparation

1. Ensure the existing `flamoris_ai` database, `db/01_schema.sql`, and
   `db/02_seed_umeko.sql` have already been applied. Do not rerun the entire
   schema against a live database as part of this migration.
2. On LIME, start the GPT-OSS llama.cpp server using the local runtime setup.
   Confirm `curl http://127.0.0.1:8081/health` and
   `curl http://127.0.0.1:8081/v1/models`. Copy the exact `data[].id` reported
   by the server; the filename or friendly name may differ.
3. From the repository root, install `requirements.txt` in a Python virtual
   environment. Copy `.env.example` to `.env` and set your PostgreSQL
   connection, `FLAMORIS_HOST_KEY=lime`, and a fresh
   `FLAMORIS_MODEL_KEY=llama.cpp:gpt-oss-20b`. Keep `.env` untracked.
   If the endpoint lists multiple models, set `INTELLIGENCE_MODEL` to the exact
   served ID. An existing model key must never be reused for a different ID.
4. Run `python apps/umeko_chat/register_runtime.py`. This explicitly adds the
   LIME host and the currently served model to the existing runtime tables.
   It refuses to repoint an existing host/model key. The old Ollama model row
   and existing runtime instances stay unchanged.
5. Run `python apps/umeko_chat/verify_db.py`, then
   `python apps/umeko_chat/chat.py`. Ask 梅子 a question and exit with `/bye`.

If the runtime manager switches GPU ownership, start the `llm` profile first.
This app never launches or stops the model server itself.

## Acceptance on LIME / decopon

After the first chat, check the new conversation and message rows in the
existing `chat` tables and the matching `runtime.instances` record. The
instance should reference the same Umeko agent ID as older instances and
the new llama.cpp model ID. Restart `chat.py` and verify the previous
conversation notice and its use as context. Exit again and confirm the
conversation/session/instance end timestamps are populated.

The tests (`python -m unittest discover -s tests -v`) use fake network and DB
responses. They verify request/response handling, model provenance, context,
message writes, and shutdown without needing GPU weights or credentials.
The real LIME/decopon acceptance above must be performed in that environment.

## Failure behavior

- An unavailable endpoint, ambiguous model list, or mismatched configured ID
  stops before creating a DB instance/conversation.
- A model row that still points at Ollama or a different served model stops
  before starting an instance. Register a new model key if the model changed.
- A failed chat request keeps the user's saved message (as the old console did),
  reports the error, and allows another message or `/bye`.

The Phase 0 client calls llama.cpp directly as authorized by Issue #2. A later
phase can move execution to Intelligence MCP without moving Agent-owned state.
