# Install and configure an Agent

This is the fresh-install path for the current single-principal console runtime.
It needs Python 3.11+, PostgreSQL with `db/01_schema.sql`, and an endpoint that
supports `GET /v1/models` and `POST /v1/chat/completions` with the OpenAI-compatible
response shape used by the current llama.cpp adapter. The current registration
records provider `llama.cpp`; compatibility with another provider is not
established merely by exposing those routes. The model service and PostgreSQL
must be reachable from the Agent process. No GPU or database is needed for CI.

## 1. Install the package

```sh
git clone https://github.com/flamoris-jp/flamoris-ai-agent.git
cd flamoris-ai-agent
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

For development use `python -m pip install -e '.[dev]'`. A normal package install
is also supported (`python -m pip install .`, or install a built wheel). Source
installs use the checkout root for `.env` and `agents/`; wheel installs use
process environment and the bundled example Agent unless an explicit deployment
home is supplied. See [Agent context](AGENT_CONTEXT.md) for that layout.

## 2. Initialize PostgreSQL

Have your administrator create the database and its owner/runtime roles with
the required permissions in your own PostgreSQL environment. Inspect the role
names and `SET ROLE` near the top of `db/01_schema.sql`; the schema expects
`flamoris_ai_owner` and grants access to `flamoris_ai_app`. As a database
administrator connected to the new database, apply the schema once:

```sh
psql -X -v ON_ERROR_STOP=1 -d flamoris_ai -f db/01_schema.sql
```

Use your PostgreSQL administration method to select host, database, and
administrator credentials. `db/02_seed_example.sql` contains synthetic sample
records for examples and tests; it is not a deployment initialization step.
`flamoris-agent-setup` below creates the actual configured identities.

## 3. Configure identities and inference

Copy `.env.example` to an untracked `.env` in the checkout (or in an explicit
deployment home) and replace its synthetic values. `PGHOST`, `PGPORT`,
`PGDATABASE`, `PGUSER`, and `PGPASSWORD` identify the PostgreSQL connection.
Keep the password private. `INTELLIGENCE_BASE_URL` is the URL reachable by the
Agent process. Check its model list, for example:

```sh
curl "$INTELLIGENCE_BASE_URL/v1/models"
```

If it exposes one model, `INTELLIGENCE_MODEL` may be unset. If it exposes
multiple models, set it to the exact `data[].id`; a mismatch fails resolution.
The URL in `.env` is not automatically exported into the shell used by `curl`,
so substitute the configured URL or export it first. A deployed GPT-OSS
llama.cpp instance is one tested Phase 0 example; see the
[historical runbook](PHASE_0_RUNBOOK.md) for that path.

| Variable | Identifies or controls | Stability / source |
|---|---|---|
| `FLAMORIS_HUMAN_KEY`, `FLAMORIS_AGENT_KEY`, `FLAMORIS_PROJECT_KEY` | Human, Agent, project DB rows; Agent key selects its directory | Deployment-chosen stable keys |
| `FLAMORIS_HUMAN_DISPLAY_NAME`, `FLAMORIS_AGENT_DISPLAY_NAME`, `FLAMORIS_AGENT_TYPE`, `FLAMORIS_PROJECT_NAME`, `FLAMORIS_PROJECT_SLUG` | Setup metadata | Chosen by deployment; existing values must match on setup rerun (type defaults to `agent`) |
| `FLAMORIS_HOST_KEY` | Runtime host DB row | Deployment-chosen stable key; current registration also checks actual OS hostname, so use a new key on a different host |
| `FLAMORIS_APPLICATION_KEY`, `FLAMORIS_APPLICATION_NAME` | Application identity and checked name | Stable key; name must match on setup rerun |
| `FLAMORIS_MODEL_KEY` | Registered DB model identity | Deployment-chosen stable key; never reuse for a different served model |
| `INTELLIGENCE_MODEL` | Served provider model | Exact `/v1/models` ID if supplied; optional only for a single model |
| `FLAMORIS_INSTANCE_LABEL` | Concrete instance row label | Optional metadata (default `console`), not an identity |

These are separate provenance identities. `FLAMORIS_HOST_KEY` need not equal the
OS hostname, though its row is tied to the hostname at registration.
`FLAMORIS_MODEL_KEY` is not the served `INTELLIGENCE_MODEL` value. Existing setup
rows reject changed names/type/slug rather than silently updating them. Context
window variables and optional MCP/HTTP settings are explained in `.env.example`.

## 4. Create your Agent context

Set `FLAMORIS_AGENT_KEY=support-agent`, then create
`agents/support-agent/agent.toml` and the referenced files in the selected home:

```toml
version = 1

[[context]]
title = "Identity"
file = "identity.md"

[[context]]
title = "Customer support"
file = "support.md"
```

For example, `identity.md` can say “You are an assistant for Example Notes.
Answer clearly.” and `support.md` can say “Example Notes stores notes and
supports tagging.” Only one section is required; custom names and ordered
sections are supported. See [Agent context](AGENT_CONTEXT.md) for validation,
source/wheel behavior, and migration of older three-file contexts.

For an installed wheel with private editable context, export
`FLAMORIS_AGENT_HOME=/absolute/path/to/deployment` before running commands.
Create that directory with `.env` and `agents/support-agent/agent.toml` and its
files. It must already exist and is authoritative. The package will not look in
an unrelated current directory or substitute `example-agent` if a custom key's
files are missing. Supply `FLAMORIS_AGENT_KEY` via that `.env` or environment.

## 5. Setup and verify

With the model endpoint running and the fresh database schema applied:

```sh
flamoris-agent-setup
flamoris-agent-verify-db
flamoris-agent-chat
```

Setup creates/checks human, Agent, project, application, runtime host, and model
rows. It resolves the served model and rejects repointing existing host/model
keys. Verification checks configured database references. The chat command
creates a conversation and runtime instance; send a harmless test message,
exit with `/bye`, then restart to check previous-conversation retrieval. The
console stores messages in PostgreSQL and closes lifecycle rows on clean exit.
Do not rerun the initial schema against an existing deployment as a routine
upgrade; inspect migrations and preserve its identities.

## 6. Optional MCP and Docker

The same single-principal Agent can expose stdio MCP via `flamoris-agent-mcp`.
Authenticated private HTTP and the repository's current Compose path are
described in [Docker deployment](DOCKER.md). Complete the basic identity and
context setup first. The Docker image packages the public example only;
private context needs an explicit read-only mount and `FLAMORIS_AGENT_HOME`.

## Troubleshooting

| Symptom | Check |
|---|---|
| Database connection or missing relation | `PG*` settings, role grants, and one-time `db/01_schema.sql` application |
| Missing identity variable | Populate all required `FLAMORIS_*_KEY` and checked name/slug values in `.env` |
| Existing key conflict | Keep original metadata, or deliberately choose a new identity key; never repoint a host/model key |
| `invalid_agent_context` | Check selected `agents/<agent-key>/agent.toml`, referenced UTF-8 files, and the key; call `load_agent_context()` locally for the specific validation error |
| Invalid `FLAMORIS_AGENT_HOME` | Export an existing absolute directory before process launch, containing the selected `.env` and `agents/` |
| Endpoint unavailable | Check URL from the process/container and model service availability |
| `ambiguous_model` or `model_absent` | Inspect `/v1/models`; choose the exact served `data[].id` for `INTELLIGENCE_MODEL` |
