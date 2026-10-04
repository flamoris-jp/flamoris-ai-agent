# Legacy internal Intelligence MCP adapter

Status: **deprecated target architecture**. This document records the current/previous migration implementation only.

FLAMORIS AI [#18](https://github.com/flamoris-jp/flamoris-ai/issues/18) and Agent [#38](https://github.com/flamoris-jp/flamoris-ai-agent/issues/38) supersede the design that made Intelligence MCP the Agent's internal execution dependency.

## Correct target

```text
AI Agent
   ↓
non-MCP ExecutionClient / internal execution interface
   ├─ local FLAMORIS AI Runtime
   ├─ direct provider API such as OpenAI Responses
   └─ vendor runtime
```

Intelligence MCP remains an external MCP facade used through the ChatGPT/MCP Hub path. Agent must not call it internally merely to reuse provider adapters.

## Current implementation baseline

Current main may still contain:

- `AGENT_INTELLIGENCE_TRANSPORT=mcp`;
- MCP endpoint/target configuration;
- model/capability discovery against Intelligence MCP;
- the MCP request/result adapter;
- locality/data-flow checks written around that transport.

These are migration inputs for removal, not the desired future architecture.

## What must be preserved during cleanup

Removing the internal MCP path must not remove the Agent's real safety/state guarantees:

- personality and immutable conversation snapshots;
- principal/session authorization and isolation;
- complete-context remote export consent;
- model/provider provenance;
- input/output/context/time bounds;
- no hidden fallback or retry after ambiguous acceptance;
- durable request/duplicate fences;
- fixed safe errors and secret redaction;
- continuation identity and model consistency.

## What the next implementation pass should remove first

1. MCP-specific internal transport selection and endpoint configuration.
2. Intelligence MCP discovery/dispatch from the Agent execution path.
3. MCP-only public-model/provider translation that exists solely because of that hop.
4. Documentation/tests that require `Agent -> Intelligence MCP` as the target dependency direction.

Keep or reuse the narrow transport-independent `ExecutionClient` request/result boundary. Re-introduce provider adapters only behind that internal boundary, with the smallest implementation needed for the actual local Runtime/API targets.

Do not redesign personality, DB state, Studio UI, AI Runtime kernel, or generation in the same cleanup.

## Compatibility

Existing deployments may still use the MCP adapter until a separately authorized implementation and rollout replaces it. Documentation changes do not alter live configuration. Do not silently fall back between old and new paths.

## Historical note

The previous detailed MCP adapter specification is preserved in Git history and linked Issues/PRs. It should not be copied into new design documents as active architecture.
