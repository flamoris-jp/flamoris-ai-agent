# Phase 0: single-principal Agent on GPT-OSS

Run the Agent on a runtime host where the llama.cpp endpoint is reachable on
`127.0.0.1:8081`. Human, Agent, project, host, application, and model identities
come from the deployment's private environment configuration.

## Preparation

1. For a fresh database, apply `db/01_schema.sql` once as the database administrator.
   Do not use deployment-specific seed data from the public repository.
2. On the runtime host, start the GPT-OSS llama.cpp server using the local runtime setup.
   Confirm `curl http://127.0.0.1:8081/health` and
   `curl http://127.0.0.1:8081/v1/models`. Copy the exact `data[].id` reported
   by the server; the filename or friendly name may differ.
3. From the repository root, run `python -m pip install -e .` in a Python virtual
   environment. Copy `.env.example` to `.env` and replace every synthetic identity
   with private deployment values. Keep `.env` untracked. If the endpoint lists
   multiple models, set `INTELLIGENCE_MODEL` to the exact served ID. An existing
   model key must never be reused for a different served model.
4. Run `flamoris-agent-setup`. It creates/updates the configured human, Agent,
   project and application records and registers the runtime host/model using the
   existing conflict checks.
5. Run `flamoris-agent-verify-db`, then `flamoris-agent-chat`. Send one harmless
   test message and exit with `/bye`.

If the runtime manager switches GPU ownership, start the `llm` profile first.
This app never launches or stops the model server itself.

## Acceptance in the deployment environment

After the first chat, check the new conversation and message rows in the
existing `chat` tables and the matching `runtime.instances` record. The
instance should reference the same Agent ID as older instances and
the new llama.cpp model ID. Restart `flamoris-agent-chat` and verify the previous
conversation notice and its use as context. Exit again and confirm the
conversation/session/instance end timestamps are populated.

The tests (`python -m pip install -e '.[dev]'` then `pytest`) use fake network and DB
responses. They verify request/response handling, model provenance, context,
message writes, and shutdown without needing GPU weights or credentials.
The real deployment acceptance above must be performed in that environment.

## Failure behavior

- An unavailable endpoint, ambiguous model list, or mismatched configured ID
  stops before creating a DB instance/conversation.
- A model row that still points at Ollama or a different served model stops
  before starting an instance. Register a new model key if the model changed.
- A failed chat request keeps the user's saved message (as the old console did),
  reports the error, and allows another message or `/bye`.

The Phase 0 client calls llama.cpp directly as authorized by Issue #2. A later
phase can move execution to Intelligence MCP without moving Agent-owned state.

