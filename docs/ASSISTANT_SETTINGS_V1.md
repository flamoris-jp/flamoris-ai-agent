# Assistant settings v1

Owners: Agent #34/#35; AI #17; Studio #56; Intelligence #8.

Agent owns personality identity/revisions, model/export grants and conversation snapshots. Studio authenticates its account, maps it through its existing server-side binding and renders an editor. Execution targets are reached through Agent's bounded non-MCP execution interface; provider credentials stay in operator-controlled adapter/runtime configuration. No new gateway repository is implied.

## Contract and admission

Opt-in `AGENT_SETTINGS_ENABLED=1` adds `models.allowed`, `personality.get`,
`personality.history`, `personality.save` to the shared MCP catalog. Legacy catalog
and fixed local configuration remain unchanged when disabled. New `sessions.open`
fields are optional `model_id` and `remote_consent`; legacy omission chooses the
operator `AGENT_DEFAULT_MODEL_ID`. The settings catalog is negotiated exactly.

`AGENT_EXECUTION_TARGETS` is a bounded array (1..16) of id, display_name,
model_key, target (the existing approved-target fields). IDs and model keys are
unique. Remote targets use data_flow=remote_authorized, provider_id=openai and
require both an operator model grant allow_remote=true and explicit user consent.
The remote authorization covers the complete assembled personality, previous turns
and explicit Studio attachment. No local-only or legacy previous transcript can be
sent remotely. No caller endpoints, credentials, policy, tools or fallback.

Selection, registry digest and source are persisted once per principal session.
Each availability/ask rechecks the session, enabled model grant and exact target
configuration digest. Configuration changes invalidate rather than retarget.
Model IDs map to registered immutable runtime.models identities. New rows must be
registered separately; existing model provenance is never rewritten. Models stay
fixed through continuations. A new model requires a new session/conversation.

Personality read/edit/history requires separate operator-controlled grants for
(delegator,human,agent); ask grants or Bearer credentials alone are insufficient.
A shared Agent is a shared revision authority. One writer changes future conversations
for all users of that Agent; UI must disclose this scope before saving.

Save requires expected_revision plus a canonical request UUID, display_name and
1..16 ordered {title,content} sections. Titles are unique, 1..80 characters, no
control characters. UTF-8 section content is nonempty; total body <=32768 bytes.
Display name <=128 characters, no controls. Runtime permissions are not editable.
Agent serializes on its personality head, authorizes again inside the transaction,
checks its durable UUID/digest fence before expected revision, inserts an immutable
version and advances the head atomically. A duplicate identical save returns the
original revision without reverting a later save; changed reuse fails. Conflict is
explicit and never force-overwritten. The same UUID/body may be submitted explicitly
after uncertainty; no automatic retry. History is read-authorized and paginated by
revision (one full revision per page); restoring copies a historical version into an ordinary
new expected-revision save. No destructive public delete.

## Context source and lifecycle

`AGENT_CONTEXT_SOURCE=file|db` defaults to file. Unknown source or missing DB revision
fails closed. DB settings never fall back to files. Explicit CLI import validates the
existing manifest/Markdown, preserves ordered titles/text and Agent UUID, and creates
a first revision without changing conversations/models or deleting originals.
Console/source/wheel/container share the loader and provenance. No restart per edit.
A conversation records immutable personality revision/content snapshot; continuation
reuses it even after saves. A new conversation reads the current revision. Personality
selection and model selection are independent. Source changes do not alter old snapshots.

## Retention and migration

Migration 004 is additive/repeatable and does not import or grant anything. Keep file
backups and take `pg_dump --format=custom` before migrating/importing. Validate restore
in a disposable database with the same roles; compare ordered imported sections and
existing conversation/model counts before switching AGENT_CONTEXT_SOURCE=db. Rollback:
stop settings writes, return explicitly to file source and the matching old application;
keep DB revisions/snapshots for recovery. Do not drop columns or rewrite provenance.

Versions/fences are retained indefinitely, at most 256 revisions per Agent; at capacity
save fails and needs an operator retention decision. Operator deletion must preserve the
current revision, any required historical recovery and save UUID fences (otherwise old
updates can replay). No automatic pruning/expiration. Principal option rows follow the
existing guarded principal retirement; conversation snapshots and request fences remain.

Runtime settings use one process and existing bounded execution. Remote API adapters must preserve input/output/time/concurrency and operator per-request cost ceilings;
usage reports token counts. These are per request, not monthly billing guarantees.
Timeout/cancel may leave remote work billable; never replay an uncertain inference.

## Review checklist

Before code: head lock/atomic revision; read vs edit; no grant creation by callers;
all-context export including history; immutable target digest/DB model mapping;
continuation snapshot; separate transport catalog; no credentials in public DTOs;
rollback/retention bounded and explicit. Self-review completed against these boundaries.
Live migration, grants, credential setup and paid API acceptance are separate from CI.

## Operator rollout

Apply db/migrations/004_assistant_settings.sql with the owning role; it creates no
grants or persona/model data. Configure the bounded target registry, then run
`flamoris-agent-register-targets` to insert only missing exact runtime model
identities without paid calls. A reused key with different provider/model fails.
Import each existing personality with
`flamoris-agent-import-personality --agent <existing-key> --display-name <name>`.
The importer validates and compares ordered bodies and preserves original files.
Provision core.model_grants and core.personality_grants as the owner, using exact
registered UUIDs. Runtime credentials can read grants but cannot mutate them.
Enable AGENT_CONTEXT_SOURCE=db and AGENT_SETTINGS_ENABLED=1. Do **not** enable or require `AGENT_INTELLIGENCE_TRANSPORT=mcp`; that internal path is deprecated by FLAMORIS AI #18. Configure only the reviewed non-MCP execution adapter required by the deployment. Set AGENT_DEFAULT_MODEL_ID to an authorized local ID;
external selection always requires explicit consent. Validate new/continued
conversation revisions and two users before enabling the matched Studio flag.
Grant reads linearize at admission. Saves reauthorize after acquiring the persona
head lock; a later grant revocation cannot retrospectively cancel an admitted save.
Principal-session revocation serializes with the existing binding lock.


## Architecture correction

This settings contract predates the internal-MCP correction. Model choice and remote-export consent remain valid Agent responsibilities, but the selected target must dispatch through the Agent's non-MCP execution interface. Intelligence MCP discovery or endpoint configuration must not be part of the future Agent settings contract.
