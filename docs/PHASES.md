# FLAMORIS AI Agent implementation and remaining phases

Current cross-repository authority is [AI #18](https://github.com/flamoris-jp/flamoris-ai/issues/18)
and [AI progress](https://github.com/flamoris-jp/flamoris-ai/blob/main/PROGRESS.md).
The original imported phase order is historical and must not reintroduce internal
MCP execution or repeat completed work.

## Implemented baseline

| Scope | Current source / evidence |
| --- | --- |
| Imported state and Phase 0 | Existing Agent/personality/conversation schema and configured local llama.cpp console; historical acceptance in [Phase 0](PHASE_0_ACCEPTANCE.md) |
| Client boundary | `ExecutionClient`, ordered messages, exact model identity and bounded results; [contract](EXECUTION_CONTRACT.md) |
| External facade | Fixed/shared Agent MCP and authenticated `/mcp`; optional external ChatGPT/Hub access |
| Internal execution | Agent #40 deletes outbound MCP and uses the shared non-MCP provider adapter; [internal HTTP/direct contract](INTERNAL_EXECUTION.md) |
| Studio integration | Principal/delegator grants, scoped sessions, Image context, durable request/continuation fences and Agent HTTP `/api/v1` |
| Assistant settings | Opt-in personality revisions and granted local/OpenAI model selection; [settings](ASSISTANT_SETTINGS_V1.md) |

Studio -> Agent HTTP -> `ExecutionClient` -> shared `flamoris_intelligence` is the
implemented personality path. Raw inference bypasses Agent. Agent stores its own
personality and conversations; provider runtime/cache state is not Agent memory.
A native AI Runtime adapter is not introduced by the shared HTTP/provider library.

Configured OpenAI targets require an explicitly granted settings session,
operator credentials/cost ceilings and consent for the whole assembled context.
Local-only or legacy-unclassified history cannot be exported. A changed target or
personality starts a fresh appropriate session; old conversations are not silently
retargeted. Logical user isolation does not promise concurrent GPU inference.

## Operational acceptance still separate

A source merge does not deploy Agent, apply its schema, create grants, qualify an
installed model or change host runtime state. Current HTTP/settings deployment
needs actual principal/DB/model/restart/two-user receipts and preserved unknown
request fences. The old Phase 0 receipt describes its old deployment only.

## Deferred functionality

- Agent-owned memory, knowledge retrieval and project continuity need a concrete
  separately reviewed storage, authorization and retention contract.
- Tool use needs explicit capability/permission policy, structured bounded calls,
  audit and side-effect uncertainty handling. Internal FLAMORIS execution uses
  non-MCP interfaces; external MCP is a facade, not the internal tool bus.
- Structured draft proposals and additional media contexts need their own revision,
  ownership, decoding and export rules. Advice does not directly edit Studio drafts
  or submit generation.
- Native Runtime integration remains separately scoped. Generation Controller
  and its bounded checkpoint registration profile are accepted in their owners;
  no removed custom graph/v3 subsystem is migrated or recreated.

Historical imported planning is preserved in `history/`. The
[pre-audit phase document](https://github.com/flamoris-jp/flamoris-ai-agent/blob/c6adca2727805a62348e2aade219ea20a8e2ee99/docs/PHASES.md)
records the former outbound-Intelligence-MCP plan; it is superseded by the implemented
internal contract and does not authorize fallback to that deleted adapter.
