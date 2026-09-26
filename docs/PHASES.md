# FLAMORIS AI Agent Phases

This document defines the staged modernization path for the imported FLAMORIS AI Agent baseline.

The goal is to preserve working Agent-owned state and behavior while replacing the old model/runtime coupling incrementally.

## Current baseline

The imported baseline already separates Agent-facing state from model identity:

```text
Agent identity / personality
Conversation
Knowledge
Memory
Runtime provenance
Relay
Ops
        │
        ▼
Model/runtime call
```

The original implementation used:

```text
Ollama
└─ Qwen-based Umeko model
```

The first modernization target is:

```text
llama.cpp
└─ GPT-OSS 20B
```

The imported PostgreSQL schema and Agent-owned state are migration inputs and should remain unchanged unless a concrete incompatibility is found.

---

## Phase 0 — Run the existing Agent on GPT-OSS

### Goal

Prove that the existing Agent architecture can run with GPT-OSS by replacing only the model/runtime integration boundary.

This phase is intentionally small.

### Runtime target

LIME currently provides the GPT-OSS runtime through llama.cpp with an OpenAI-compatible HTTP API.

Expected local endpoint:

```text
http://127.0.0.1:8081
```

Expected chat endpoint:

```text
POST /v1/chat/completions
```

### Preserve as-is unless required

Do not redesign these areas in Phase 0:

- Agent identity
- Umeko personality and character context
- prompt/context composition
- PostgreSQL schema
- conversations
- messages
- previous-conversation loading
- knowledge tables
- memory tables
- relay tables
- ops tables
- runtime provenance model

### Change

Replace the current Ollama-specific request path with a small intelligence client boundary.

Recommended shape:

```text
src/flamoris_ai_agent
      │
      ▼
IntelligenceClient
      │
      ▼
llama.cpp OpenAI-compatible API
      │
      ▼
GPT-OSS 20B
```

The first implementation may support only llama.cpp.

Do not introduce a large provider framework in this phase.

### Configuration

Remove direct Ollama assumptions from the active runtime path.

Configuration should describe the intelligence endpoint rather than an Ollama installation.

Example conceptual values:

```text
INTELLIGENCE_BASE_URL=http://127.0.0.1:8081
INTELLIGENCE_MODEL=<model id exposed by llama.cpp>
```

Exact variable names may be selected during implementation, but they should not encode Ollama if the value is provider-neutral.

### Required validation

Phase 0 is complete when all of the following are confirmed:

1. GPT-OSS is reachable through the configured llama.cpp endpoint.
2. Umeko starts successfully.
3. A user message receives a GPT-OSS response.
4. The conversation is written to PostgreSQL.
5. The runtime instance is recorded.
6. The Agent exits cleanly.
7. After restart, the previous conversation can be loaded.
8. Existing Agent identity remains stable across the model switch.
9. No real credentials or machine secrets are added to the repository.

### Explicitly out of scope

- redesigning Memory
- adding pgvector
- redesigning Knowledge retrieval
- implementing long-term memory extraction
- tool execution
- multi-agent orchestration
- replacing the PostgreSQL schema
- introducing a daemon/service architecture
- moving to Intelligence MCP
- UI work
- migration to a new programming language/framework

---

## Phase 1 — Stabilize the Agent runtime boundary

### Goal

After Phase 0 proves the old architecture still works, isolate model execution cleanly from Agent-owned state.

Likely work:

- define a narrow intelligence client interface;
- normalize request/response/error handling;
- remove remaining provider-specific assumptions from Agent code;
- add focused tests around prompt construction, conversation persistence, and provider failure behavior;
- document ownership boundaries between Agent state and intelligence execution.

The implementation should remain provider-neutral, but should avoid speculative abstraction.

---

## Phase 2 — Intelligence MCP integration

### Goal

Replace direct llama.cpp access with the FLAMORIS Intelligence MCP when that boundary is ready.

Target:

```text
flamoris-ai-agent
        │
        ▼
flamoris-intelligence-mcp
        │
        ▼
provider/runtime
        │
        └─ llama.cpp / GPT-OSS
```

The Agent remains authoritative for:

- persistent Agent identity;
- conversations;
- memory;
- knowledge references and retrieval context;
- prompts and Agent policy;
- long-lived Agent workflow context.

Intelligence MCP remains authoritative for model/provider execution and routing.

Phase 2 should not require a rewrite of Agent persistence.

---

## Phase 3 — Memory and Knowledge evolution

Only after the GPT-OSS runtime path is stable should the imported Memory/Knowledge design be reviewed.

Possible work:

- durable memory lifecycle;
- provenance;
- retention/deletion;
- memory visibility and sharing;
- retrieval rules;
- pgvector or another retrieval index;
- memory candidate extraction from conversations.

The imported schema is a useful starting point, not automatically the final design.

---

## Phase 4 — Tools and orchestration

Add explicit Agent capabilities only after the Agent runtime and memory boundaries are stable.

Possible work:

- tool registry;
- capability checks;
- auditable tool calls;
- explicit product commands/queries;
- Generation MCP integration;
- persistent orchestration metadata;
- bounded multi-agent coordination.

Product repositories remain authoritative for their own document and editing state.

---

## Migration principle

Prefer this sequence:

```text
preserve
→ run
→ observe
→ isolate
→ modernize
```

Do not redesign working Agent-owned state merely because the model runtime changes.

The first question for every migration should be:

> Does this belong to the Agent, or was it only an implementation detail of the old model runtime?

If it belongs to the Agent and still works, preserve it until evidence shows a reason to change it.

