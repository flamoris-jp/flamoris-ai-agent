# FLAMORIS AI Agent

Optional persistent personality and conversation layer for FLAMORIS. Agent owns identity/personality, conversation/session state, memory/context policy and Agent-specific prompt assembly. It is not the mandatory entry point for raw inference or generation.

## Current implementation and target

The packaged console and bounded Agent MCP surface are implemented. Phase 0 GPT-OSS/llama.cpp acceptance is recorded in #2; this is historical evidence, not a current host-health claim. Persisted principal sessions, bounded Studio context and opt-in personality/model settings have their own contracts linked below. General Memory CRUD, general tools and durable cross-service orchestration are not claimed complete.

[AI #18](https://github.com/flamoris-jp/flamoris-ai/issues/18) and [Agent #38](https://github.com/flamoris-jp/flamoris-ai-agent/issues/38) correct the target dependency direction:

```text
Target internal path:
Studio Agent Support -> AI Agent -> narrow non-MCP execution interface
                                      -> local Runtime / API / vendor runtime

Separate external path:
ChatGPT -> MCP Hub -> Intelligence MCP -> approved internal capability
```

The [internal HTTP and direct execution contract](docs/INTERNAL_EXECUTION.md) is implemented: Studio uses `/api/v1`, and approved execution targets reuse the shared non-MCP Intelligence provider library. The outgoing Intelligence MCP client was deleted. The transport-independent [ExecutionClient boundary](docs/EXECUTION_CONTRACT.md) and Agent state/consent/fences remain authoritative.

An inbound external Agent MCP adapter and an outbound Agent-to-Intelligence MCP client are different things. Removing the latter does not authorize deleting every external MCP tool. Studio's internal inbound MCP use also needs its own caller/contract audit.

The earlier internal-connection cleanup changed no DB schema. Subsequently, Agent #43 and Studio #66 implemented same-conversation model switching with additive source migrations (Agent 005 and Studio 20261005_12). Controller and its bounded ComfyWorkFlow/reference-image profile are also accepted in main. No live migration, grant mutation, deployment or paid inference has been performed; see [AI progress](https://github.com/flamoris-jp/flamoris-ai/blob/main/PROGRESS.md).

## Existing contracts

- [Same-conversation model switching](docs/MODEL_CONTINUATION.md) is implemented in
  Agent #43, matched with Studio #66 and source migration 005; deployment acceptance remains pending.

- [Installation](docs/INSTALL.md) and [Agent context](docs/AGENT_CONTEXT.md)
- [ExecutionClient](docs/EXECUTION_CONTRACT.md)
- [Fixed-principal MCP contract](docs/MCP_CONTRACT.md)
- [Persisted principal sessions](docs/PRINCIPAL_SESSIONS.md) and [bounded retirement](docs/PRINCIPAL_RETENTION.md)
- [Bounded Image context and ask availability](docs/STUDIO_CONTEXT_V1.md)
- [Current opt-in settings](docs/ASSISTANT_SETTINGS_V1.md)
- [Corrected Studio design](docs/STUDIO_ASSISTANT.md)
- [Docker reference](docs/DOCKER.md)

Existing deployment runbooks do not authorize live cutover. Review the exact configuration migration and preserved state/fences in the internal contract before any separately authorized rollout.

## Baseline and layout

The imported `flamoris_ai` baseline, earlier design notes and retired Ollama definitions are retained as history, not current architecture. Secrets were not imported; real `.env` stays untracked.

| Path | Responsibility |
| --- | --- |
| `src/flamoris_ai_agent/` | Active package and entry points |
| `agents/example-agent/` | Synthetic packaged example |
| `db/` | PostgreSQL schema, migrations and synthetic seed |
| `tests/` | Offline/provider/DB fixture and package tests |
| `docs/` | Current contracts, design and runbooks |
| `history/` | Imported/retired records |

Use the installation guide for `flamoris-agent-setup`, `flamoris-agent-chat`, `flamoris-agent-register-runtime` and `flamoris-agent-verify-db`; `python -m flamoris_ai_agent.chat` is also supported. Source/editable installs use repository `.env` and `agents/`; wheel installs default to bundled context and process environment. `FLAMORIS_AGENT_HOME` selects private context as described by the context contract; missing selected context fails rather than choosing another Agent. The public example seed is not a deployment setup path.

```sh
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
pytest
python -m build
```

Normal tests require no paid API, GPU, private persona or model weights. Actual PostgreSQL/provider/deployment evidence remains separate.

## Existing MCP scope

The fixed-principal stdio entry is `flamoris-agent-mcp`, with `health` and `ask`. `ask` uses `request_id`, `text` and optional `previous_conversation_id`, creates/closes a conversation and enforces the documented owner scope and durable duplicate fence. An uncertain attempt must not be replayed with a new UUID automatically. Console history is not exposed through unscoped lookup.

Opt-in shared HTTP principal/session and settings catalogs are separate contracts, not a claim that the fixed-principal stdio endpoint is multi-user. A transport token does not identify a human. Preserve independent membership/delegation checks, compatible continuation identity and current availability semantics. Inference and PostgreSQL remain external to the container; the current deployment reference is not changed here.

## Ownership and terminology

AI Runtime owns model-adjacent inference, ExecuteFlow, the distinct compiled ExecutionPlan, active Jobs/Continuations and resources. ComfyWorkFlow means ComfyUI graph/JSON, not an Agent flow or all media requests. Generation-domain jobs/inputs/assets remain outside Agent; Generation MCP is the external facade and the implemented Controller owns the shared generation domain. GPU Node Manager retains host lifecycle authority.

Products own their document, editing, revision and permission state. Agent may assist through explicit granted contracts, not shadow copies or ambient tool authority. Commons owns generic infrastructure. Personality and model selection remain independent; provider configuration and secrets never become persona or memory.

Knowledge, drafts, prior messages and model output are untrusted data, not permission or policy. Preserve principal isolation, immutable persona snapshots, complete-context remote consent, bounded I/O, safe errors, provenance and request fences during later cleanup. Local failure is not permission for remote fallback. No new Agent, generation or model features are part of removing a transport.

## 日本語

AI Agentは人格が必要なときだけ使う層です。人格・会話・記憶・principal/sessionを維持し、Studioは内部HTTP、推論は共有の非MCPアダプターで接続します。外向けMCP入口は維持し、内部Intelligence MCPクライアントは削除しました。実機の切替は行っていません。

ExecuteFlowと既存ExecutionPlanはRuntime側、ComfyWorkFlowはComfyUI側です。Controllerと会話内LLM切替は担当mainへマージ済みです。実機反映・migration適用は未実施です。

## Policy and license

Follow the [FLAMORIS repository policy](https://github.com/flamoris-jp/flamoris-commons/blob/main/docs/repository-policy.md). Source and documentation are [Apache-2.0](LICENSE) unless otherwise noted. Models, weights, datasets, retrieved content, third-party prompts and generated media may have separate terms. Software is provided as-is without guaranteed individual support; repository documentation, Issues, tests and source are the primary references.

## Updater entry release 1.0.0

See [Updater compatibility](docs/UPDATER.md) for the implemented admission/Owner
contract and pending signed release/private provisioning/real-host acceptance.
