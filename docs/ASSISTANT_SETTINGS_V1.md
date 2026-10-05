# Assistant settings v1: current implementation reference

Original owners: Agent #34/#35, AI #17, Studio #56 and Intelligence #8. Architecture correction: [AI #18](https://github.com/flamoris-jp/flamoris-ai/issues/18) and [Agent #38](https://github.com/flamoris-jp/flamoris-ai-agent/issues/38).

**This document describes the opt-in settings domain and its retained state/policy.** The implemented [internal HTTP and direct execution contract](INTERNAL_EXECUTION.md) replaces the old internal MCP hops. Source cleanup changes no DB schema, grants or existing persona/conversation records and performs no operational rollout.

Agent owns persona identity/revisions, model/export grants and conversation snapshots. Studio authenticates its account and renders its authorized editor. Operator-approved targets use the shared stateless non-MCP provider library; provider credentials remain operator configuration. Persona and grants stay with Agent.

## Existing contract and admission

`AGENT_SETTINGS_ENABLED=1` adds `models.allowed`, `personality.get`, `personality.history` and `personality.save` to the shared MCP catalog. Disabled settings preserve the legacy catalog/fixed local configuration. Optional `sessions.open` fields are `model_id` and `remote_consent`; omission chooses `AGENT_DEFAULT_MODEL_ID` under the existing contract.

The implemented registry variable is **`AGENT_INTELLIGENCE_TARGETS`**. This literal is read by `src/flamoris_ai_agent/model_settings.py`; do not substitute an invented replacement name in configuration. It is a bounded array of 1-16 entries with id, display_name, model_key and target. IDs/model keys are unique. Remote targets use `data_flow=remote_authorized`, `provider_id=openai`, an operator grant with `allow_remote=true` and explicit consent.

Authorization covers the full assembled personality, previous turns and explicit Studio attachments. Local-only/legacy history is not exported. Callers supply no endpoint, credential, policy or tool grant. There is no hidden fallback.

Selection, registry digest and source are persisted per principal session. Availability/ask recheck session, enabled grant and exact target digest. A configuration change invalidates rather than retargets. IDs map to separately registered immutable `runtime.models` identities; history/provenance is not rewritten. Each principal session keeps its immutable selected model. Explicit internal [model continuation](MODEL_CONTINUATION.md) creates an authorized same-principal child session while preserving the logical conversation and original personality snapshot; it never silently retargets an existing session.

## Personality revisions and permissions

Read/edit/history need separate operator grants for delegator/human/agent. Ask access or a bearer token alone does not authorize editing. Shared Agent revisions affect future conversations for all authorized users; disclose the sharing scope.

Save requires `expected_revision`, a canonical request UUID, display_name and 1-16 ordered title/content sections. Titles are unique, 1-80 characters, with no controls; UTF-8 content is nonempty and total body is at most 32768 bytes. Display name is at most 128 characters with no controls. Runtime permissions are not editable persona text.

Under the persona head lock, reauthorize in the transaction, check durable UUID/digest fencing before expected revision, insert an immutable version and advance the head atomically. Identical duplicate saves return the original revision without rolling back a newer head. Changed UUID reuse and revision conflict fail explicitly. An explicit retry of the same UUID/body after uncertainty is distinct from automatic retry.

History is read-authorized and paginated one complete revision per page. Restore copies historical content through an ordinary expected-revision save. There is no destructive public delete.

## Context source and lifecycle

`AGENT_CONTEXT_SOURCE=file|db` defaults to file. Unknown source/missing selected DB revision fails closed; DB mode does not fall back to files. Explicit import preserves ordered titles/text and Agent UUID, creates the first revision and leaves original files/conversations/models intact.

Console/source/wheel/container use the same loader/provenance. A conversation fixes a persona revision/content snapshot; continuation keeps it after edits. New conversations read the current revision. Persona choice and model choice are independent. Source changes do not rewrite old snapshots; editing DB persona content does not require a restart per edit.

## Persistence and limits

Migration 004 is additive/repeatable and creates no grants or imported persona data. Any later authorized import/migration must first preserve files and take a custom-format PostgreSQL backup, verify restoration with the same roles and compare ordered content plus existing conversation/model counts. Rollback must retain DB revisions/snapshots; no dropping columns or rewriting provenance.

Versions/fences are retained indefinitely, up to 256 revisions per Agent; capacity exhaustion requires an operator retention decision. Preserve current/recovery revisions and save fences during any separately authorized deletion. No automatic pruning. Principal options follow guarded retirement; conversation snapshots and request fences remain.

Existing service concurrency and execution limits remain. Direct remote requests use the shared Intelligence adapter input/output/time/concurrency and operator-configured per-request cost bounds. Token/cost metadata is not a monthly billing guarantee; timeout/cancel does not prove unbilled remote cancellation. Never replay uncertain inference.

## Rollout hold and target migration

Operational migration/import/grant or transport cutover requires its own authorization. `AGENT_INTELLIGENCE_TRANSPORT=mcp` and a nonempty old MCP endpoint are explicitly rejected. The approved direct route and the unchanged registry are documented in INTERNAL_EXECUTION.md. Existing sessions with the former execution digest invalidate instead of changing provider under their saved identity.

The [pre-correction rollout reference](https://github.com/flamoris-jp/flamoris-ai-agent/blob/e949678efdee18219ceedbed650df097ed62a52f/docs/ASSISTANT_SETTINGS_V1.md) preserves exact historical commands and configuration. It is an as-built reference, not permission to deploy the rejected route anew.

The implemented internal contracts retain model/persona identities, snapshots, consent, grants and fences; there is no silent fallback. Review current grants at admission, and reauthorize persona saves under the head lock. Revocation cannot retroactively cancel an already-admitted committed save; principal-session revocation keeps its existing binding lock semantics.

## Acceptance

Retain tests for head-lock/atomic revision, read versus edit, complete-context export, immutable target/configuration mapping, continuation snapshots, exact HTTP/external MCP catalogs, credential isolation and rollback/retention. CI PostgreSQL fixtures and live provider/two-user deployment acceptance remain different evidence. No deployment migration is claimed by source cleanup.
