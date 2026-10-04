# Assistant settings v1: current implementation reference

Original owners: Agent #34/#35, AI #17, Studio #56 and Intelligence #8. Architecture correction: [AI #18](https://github.com/flamoris-jp/flamoris-ai/issues/18) and [Agent #38](https://github.com/flamoris-jp/flamoris-ai-agent/issues/38).

**This document describes the existing opt-in implementation, including its legacy MCP path. It is not a rollout instruction for the corrected architecture.** No code/configuration/DB change is made by this documentation PR. The replacement non-MCP transport and its configuration have not been implemented here.

Agent owns persona identity/revisions, model/export grants and conversation snapshots. Studio authenticates its account and renders its authorized editor. Currently, the configured MCP-backed targets and provider credentials follow the existing Intelligence service path. The corrected target replaces that internal MCP dependency; it does not move persona or grants to another owner.

## Existing contract and admission

`AGENT_SETTINGS_ENABLED=1` adds `models.allowed`, `personality.get`, `personality.history` and `personality.save` to the shared MCP catalog. Disabled settings preserve the legacy catalog/fixed local configuration. Optional `sessions.open` fields are `model_id` and `remote_consent`; omission chooses `AGENT_DEFAULT_MODEL_ID` under the existing contract.

The implemented registry variable is **`AGENT_INTELLIGENCE_TARGETS`**. This literal is read by `src/flamoris_ai_agent/model_settings.py`; do not substitute an invented replacement name in configuration. It is a bounded array of 1-16 entries with id, display_name, model_key and target. IDs/model keys are unique. Remote targets use `data_flow=remote_authorized`, `provider_id=openai`, an operator grant with `allow_remote=true` and explicit consent.

Authorization covers the full assembled personality, previous turns and explicit Studio attachments. Local-only/legacy history is not exported. Callers supply no endpoint, credential, policy or tool grant. There is no hidden fallback.

Selection, registry digest and source are persisted per principal session. Availability/ask recheck session, enabled grant and exact target digest. A configuration change invalidates rather than retargets. IDs map to separately registered immutable `runtime.models` identities; history/provenance is not rewritten. Continuations keep the selected model; changing it requires a new session/conversation.

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

Existing service concurrency and execution limits remain. Current MCP-backed remote requests use the configured Intelligence adapter input/output/time/concurrency and per-request cost bounds. A later non-MCP adapter must preserve equivalent applicable guarantees. Token/cost metadata is not a monthly billing guarantee; timeout/cancel does not prove unbilled remote cancellation. Never replay uncertain inference.

## Rollout hold and target migration

Do not execute migration/import/grant or transport changes from this documentation review. In the current MCP-backed setup, `AGENT_INTELLIGENCE_TRANSPORT=mcp` is still an implemented mode used by the settings path. Its architectural deprecation does not make the current service work without it. Do not disable it or enable an unimplemented replacement based only on this document.

The [pre-correction rollout reference](https://github.com/flamoris-jp/flamoris-ai-agent/blob/e949678efdee18219ceedbed650df097ed62a52f/docs/ASSISTANT_SETTINGS_V1.md) preserves exact historical commands and configuration. It is an as-built reference, not permission to deploy the rejected route anew.

The later Intelligence task must specify the minimum non-MCP execution and Studio-to-Agent contracts, exact configuration migration, caller/error behavior and retained guarantees before deleting the old path. Keep model/persona identities, snapshots, consent, grants and fences; do not silently fallback. Review current grants at admission, and reauthorize persona saves under the head lock. Revocation cannot retroactively cancel an already-admitted committed save; principal-session revocation keeps its existing binding lock semantics.

## Acceptance

Retain tests for head-lock/atomic revision, read versus edit, complete-context export, immutable target/configuration mapping, continuation snapshots, exact transport catalogs, credential isolation and rollback/retention. Normal CI and live PostgreSQL/provider/two-user acceptance remain different evidence. No new feature, renamed setting or migrated deployment is claimed by this documentation correction.
