# Studio contextual assistant integration

Status: proposed Agent contract design, 2026-10-02. Coordination: [FLAMORIS AI #15](https://github.com/flamoris-jp/flamoris-ai/issues/15). Multi-principal prerequisite: [#18](https://github.com/flamoris-jp/flamoris-ai-agent/issues/18). No existing health/ask request shape is changed by this documentation PR.

## Baseline and target boundary

Implementation progress: exact persisted grants and opt-in shared HTTP sessions
are described in [PRINCIPAL_SESSIONS.md](PRINCIPAL_SESSIONS.md). The approved
local-only synchronous execution adapter is described in
[INTELLIGENCE_MCP.md](INTELLIGENCE_MCP.md). Limited Image context revision 1 and
read-only scoped prerequisite availability are described in
[STUDIO_CONTEXT_V1.md](STUDIO_CONTEXT_V1.md). These do not activate Studio
assistance or implement remote export/proposal/additional-media policy below.

Main `aadda1bfc85cc734c475eee033227e37150770fa` implements a fixed-principal service. ask takes request_id, text and optional previous_conversation_id, creates one new conversation, closes it and preserves a durable duplicate fence. health reports process liveness/busy with dependencies=not_checked. The current IntelligenceClient is a bounded temporary direct llama.cpp adapter; provider-neutral Intelligence MCP execution is a migration, not already present.

Studio's right-side assistant and standalone Assistant should call Agent, not own model/provider policy themselves. Agent owns identity/personality, persistent conversation, prompt assembly, context policy and allowed intelligence-target selection. Intelligence MCP owns raw execution and provider adapters/configuration/credentials. Hub routes these services without choosing a model. GPU Node Manager owns runtime transitions; assistance does not implicitly wake/switch the GPU.

## Principal and session establishment

Implement #18 first. Authenticated service access must be separate from authorized human/agent/project principal selection. A shared transport token is not a human identity. Studio maps its authenticated account to a verified stable principal using server-side authorization; Agent independently validates membership and transport's allowed delegation scope. Reject unbound mappings before conversation creation.

An Agent session binds the resolved principal immutably. New principal or Agent selection creates a new session; continuation across incompatible scope is rejected. Request ids, parents, conversation/proposal identifiers and provenance are scoped to the immutable principal and authorized session. Never reuse a mutable global AgentSession/provider selection across callers. Keep current fixed-principal launch configuration as explicit compatibility mode, never a silent fallback for a failed shared-principal request.

Session establishment/delegation authentication and exact transport envelope belong to #18. Structured tool arguments alone cannot establish a trusted principal. Revoked membership invalidates new requests/continuations; admitted requests follow an explicit revocation/cancellation policy and cannot gain new tools while running. Concurrent principals may be logically separate while service concurrency remains bounded; no promise of physical concurrent GPU inference.

## Context envelope

Proposed versioned context fields (extension to be reviewed before adding to ask): category/operation, product_context_id, draft_revision, whitelisted draft fields, selected Workflow id/version/digest/public profile metadata, and selected asset descriptors. Limits must cover the complete UTF-8 context including prior transcript and final prompt, not each field independently. Preserve the existing 16 KiB user-text ceiling and 64 KiB combined execution-context ceiling from EXECUTION_CONTRACT.md unless a reviewed contract changes them; the latter includes trusted personality, transcript, draft envelope and serialization overhead. Check the final serialized Intelligence request against its configured UTF-8 and conservative model-context/token limits too. The tightest applicable bound wins; reject oversize rather than silently truncate meaning.

Studio constructs the envelope from explicit user-selected attachment scope and current authorized draft. Agent validates shape/revisions/field counts and consumes it as untrusted data. Neither draft text, Workflow description nor asset metadata may alter personality/system policy/tool grants. Context cannot contain provider URLs, paths, secrets or executable commands. Product-context/revision identifiers are correlation only, not authorization.

Initial context transfer is text/metadata only; raw media is absent. Future asset-reading tools require an expiring scoped gateway grant bound to principal/request/allowed asset and operation, with actual-byte/decode/retention limits and revocation. Agent does not accept arbitrary asset IDs as proof of access or fetch arbitrary URLs. Credentials stay in server configuration. A context text compatibility shim cannot claim this structured schema or shared-user security gate is implemented.

## Persistence and context lifecycle

Agent remains authoritative for conversations. Explicitly attached context may be persisted as conversation input under documented retention/access/deletion policy and safe provenance. Do not automatically promote editor drafts into long-term Memory or knowledge. Store source product revision and attached-context selection/digest where useful without embedding credentials. Studio retains authorized view/reference mappings and unsent questions, not a competing Agent transcript store.

Provider change does not change Agent identity or rewrite prior provenance. Prior conversation is reassembled as bounded explicit untrusted context under the existing parent rules, not transferred model-internal state. Runtime caches, provider sessions and credentials never become Agent memory. Logout/revocation blocks future access even if a caller retained an old conversation UUID.

## Intelligence execution migration and target policy

Migrate the current narrow Agent execution interface onto Intelligence MCP's reviewed synchronous inference.execute contract. Map bounded messages/personality/previous transcript into explicit instruction/input preserving the trust boundary; do not flatten untrusted transcript into a trusted system instruction. Preserve context/output limits, fixed safe errors, identity/provenance, timeout/cancellation and no hidden retries. Record that inference.execute has only request-scoped execution_id and no persistent polling job.

This adapter needs explicit identity translation: the current Agent uses ModelIdentity(provider="llama.cpp", model=<served identity>) and validates it against a DB runtime model row, while Intelligence exposes configured public model_id and provider_id="llamacpp". Resolve an operator-approved mapping to the matching runtime/model references before creating the request's AgentSession/conversation, and validate returned model_id/provider_id/capability_id against that dispatch. Do not equate an arbitrary public alias with a DB model or rewrite historical provenance. Target changes create an isolated execution/session context with the correct runtime references while retaining authorized Agent identity and explicit closed-parent continuation; never mutate a started AgentSession's resolved identity.

Explicitly request supported max_output_tokens and timeout rather than inheriting Intelligence defaults. Intersect the Agent's 4096-token output ceiling, 64 KiB text ceiling and 120-second inference deadline with the configured Intelligence/model bounds and remaining request budget; serialization/envelope bounds also apply. Normalize MCP isError and ok/error independently of transport success. Validate finish_reason and bounded nonblank text: a length-terminated/empty output is not a completed Agent answer. Initially return a fixed incomplete-output error without assistant-success persistence; exposing a marked partial answer requires a separately versioned Agent result contract. Preserve the committed user turn/duplicate fence and do not retry with a larger budget.

Agent policy selects among operator-configured public intelligence model/capability identities allowed for the principal and requested data-flow class. Intelligence MCP implements provider adapters, credentials and actual registry resolution. Agent must not introduce a duplicate provider HTTP router, runtime-switching engine or secret registry. If multiple remote adapters are needed, add them in Intelligence MCP through separate owning issues.

Data-flow permission applies to the complete assembled request: trusted personality where included, the selected previous transcript, attached draft/asset metadata and new question. Re-evaluate their combined classification/retention restrictions for every selected target before dispatch; permission to send the new question alone does not authorize exporting an earlier local-only conversation. Unknown classifications fail closed, and no history is silently omitted to bypass a refusal.

Local failure does not imply permission to send a private prompt/draft to a remote API. Selection/fallback must be an explicit configured and user-authorized data-flow policy, record safe target provenance and bounded policy reason, and obey cost/context/effect limits. Default behavior is failure/unavailable rather than a new remote attempt. A target change before dispatch is a policy decision; a retry after uncertain acceptance is never justified by changing targets. APIs are examples of possible targets, not claims of current remote-provider support.

## Availability contract

Add a reviewed Agent-owned availability query, either versioned health enrichment or a new explicitly cataloged tool. Keep current liveness semantics compatible. For an authorized principal/session report bounded ask availability and reason: ready, offline, starting, busy, unavailable or unknown; include observation freshness and supported context/proposal revisions. It must check enough DB/principal/configured intelligence-target prerequisites to distinguish usability from alive. It does not promise future success or enumerate private model topology/users.

The query must not invoke paid inference, create a conversation, activate a runtime or read private transcripts. Unknown/dependencies-not-checked is unavailable for the shared assistant. Cache probes only with bounded freshness and scope; admission rechecks current membership, target, input/context bounds, deadlines and resource availability.

An Agent relying on an offline local target is unavailable; an Agent explicitly authorized/configured for a reachable API target may be ready independently of the local GPU. Only Agent sees that policy/target distinction; Studio receives safe ask availability. Busy remains a transient admission state, not a reason to switch models. UI state is preserved by Studio while disabled.

## Requests, uncertainty and proposals

Preserve request-scoped durable duplicate fencing and exact-scope closed-parent continuation. Freeze the authorized context revision/selection, chosen target-policy decision and parent with the request identity before dispatch; an uncertain request never reassembles itself from a newer draft or changed target. The current duplicate contract returns no cached answer and has no payload-digest conflict/recovery API: any future such extension needs an explicit reviewed schema and persistence contract. No new request ID may be generated automatically after an uncertain result. A duplicate means a previous admitted attempt exists, not cached success; current ask does not provide recovery lookup. Any future request-status/result endpoint must be separately authorized, scoped and retention-bounded before Studio relies on it. Disconnect/timeout cannot fabricate an answer or successful stop. Agent persistence cleanup follows its own contract, not a Studio-generated job state.

First assistant integration returns text only with safe request/conversation/model provenance. Structured product/composition proposals are a later bounded extension with base draft revision, allowed patch fields, typed parameters, exact selected Workflow/include identities and originating request. Model-generated tool names/paths/commands are never executable authority. Agent proposes; Studio authorizes and Applies against the current revision; Generation validates/registers/verifies candidate media compositions. Agent neither edits the live Studio draft nor marks production Workflow ready.

Generation/tool invocation is initially absent. A later granted capability may request a media job with explicit owner/provenance and approved operation scope. AI Agent must not mirror Generation JobStore, input/assets or Runtime scheduler. Observation references are not transferable permission. No hidden destructive operation, background generation or GPU activation is bundled into asking for advice.

## Acceptance and delivery

1. #18 principal/session isolation and compatibility; two humans/Agents/projects cannot impersonate or share parents/request records.
2. Intelligence MCP execution adapter with fake contract tests, real scoped acceptance and stable prompt trust boundaries; existing console behavior remains supported.
3. Availability/context extension with explicit catalog/transport version review; unknown dependencies disable shared assistance.
4. Studio right-side and standalone gateway acceptance; explicit context sharing and no local-to-remote fallback without policy.
5. Optional typed proposals/tools only after distinct scope/permission/lifecycle review.

Tests cover forbidden principal before DB write; membership revocation; concurrent prompt/provider/principal isolation; closed-parent cross-scope refusal; injected context and oversized combined prompt; remote-policy refusal; public-alias/DB identity mismatch before conversation creation; model/capability result mismatch; serialized input/model context overflow; output length termination without completed-answer persistence; local-only parent transcript refused on remote switch; offline target versus allowed remote target; busy and stale health; duplicate/uncertain persistence without replay; stale-draft proposals and candidate readiness ownership. Normal CI needs no live GPU, paid API or private conversation. Actual PostgreSQL/provider restart and multi-principal deployment acceptance remain separate gates.

## Tracking

Owning follow-up: [#24](https://github.com/flamoris-jp/flamoris-ai-agent/issues/24). Cross-repository acceptance stays coordinated by [FLAMORIS AI #15](https://github.com/flamoris-jp/flamoris-ai/issues/15).
