# Studio contextual assistant: corrected target

Authority: [AI #18](https://github.com/flamoris-jp/flamoris-ai/issues/18), [Agent #38](https://github.com/flamoris-jp/flamoris-ai-agent/issues/38) and [Studio #62](https://github.com/flamoris-jp/flamoris-studio/issues/62). The earlier #15/#24 integration assumptions are superseded where they require internal MCP. Their valid requirements/evidence are retained, not reimplemented from this document.

## As-built versus target

Current persisted grants/sessions are described in [PRINCIPAL_SESSIONS.md](PRINCIPAL_SESSIONS.md), limited Image context/availability in [STUDIO_CONTEXT_V1.md](STUDIO_CONTEXT_V1.md), and opt-in settings in [ASSISTANT_SETTINGS_V1.md](ASSISTANT_SETTINGS_V1.md). The [implemented internal contract](INTERNAL_EXECUTION.md) replaces both old MCP hops with Agent HTTP and shared direct provider execution. A historical single-principal snapshot is not the latest implementation inventory.

```text
Target: Studio Agent Support -> internal non-MCP Agent contract
          -> AI Agent -> ExecutionClient -> Runtime / API / vendor runtime
```

Agent Support supplies personality/conversation. Raw inference and generation bypass Agent when no personality is requested. Studio uses `/api/v1`; Agent reuses the non-MCP `flamoris_intelligence` library. External ChatGPT/MCP Hub facades remain separate. Native Runtime embedding is a separate scope; there is no new universal execution service.

## Principal and session guarantees to retain

Transport authentication is not a human identity. Studio binds its authenticated account to an authorized principal; Agent independently verifies membership and delegator scope before state creation. Do not redo completed principal work merely because an old proposal said 'implement first'.

Bind human/Agent/project immutably to the session. Scope request IDs, parents, conversations and provenance to that authorization. A new principal/model uses a new appropriate session; reject cross-owner continuation. Do not share a mutable global AgentSession across callers or fall back to a default principal after rejection. Keep revocation/admission semantics and bounded concurrency; logical isolation does not promise simultaneous GPU inference.

## Context and persistence

Preserve the existing 16 KiB question and 64 KiB combined execution-context ceilings unless a separately reviewed contract changes them. Include personality, selected prior transcript, draft metadata and serialization overhead. Apply tighter target/model/serialized-input limits too. Reject oversize rather than silently truncating or dropping private history to bypass an export refusal.

Studio constructs context from explicit selected attachment scope and authorized draft revision. Agent treats draft text, prior messages, asset descriptions and ComfyWorkFlow metadata as untrusted data. None grants system policy, tool access or credentials. IDs/digests are correlation, not authorization. ComfyWorkFlow metadata means a ComfyUI graph descriptor, not every media recipe and not ExecuteFlow/ExecutionPlan.

Use the actually implemented bounded context contract; proposed extra media or asset-reading tools require a separate scope, authorization, expiry, decoding/size and retention design. Do not fetch arbitrary URLs/paths or pretend a text shim implements a new media schema.

Agent remains the durable conversation/persona owner. Explicitly attached context may be persisted only under documented access/retention rules; it is not automatically long-term memory. Studio retains authorized references and unsent draft/question state, not a competing transcript/persona DB. Continuations keep persona/model snapshots and prior provenance. Runtime caches/provider sessions never become Agent memory.

## Execution and availability

Use the narrow [ExecutionClient contract](EXECUTION_CONTRACT.md) in the corrected target. The later removal inventory must retain genuine identity/budget/provenance checks and remove only translation required by the obsolete MCP hop. Do not duplicate adapters or introduce a central service merely to make them replaceable.

Target/export selection remains policy over authorized configured identities. A remote request requires consent for all assembled personality/history/attachments, not only the newest text. Unknown classification or local-only/legacy history fails closed. Local outage or busy does not authorize remote fallback. Credentials stay in operator configuration, never browser fields, persona or prompts.

Reuse current Agent-owned scoped availability. It must distinguish process liveness from checked prerequisites without inference, conversation creation, paid calls, transcript reads or GPU activation. Unknown/stale prerequisites disable the applicable action. Recheck membership/target/input/budgets on admission. A configured authorized API may be usable independently of an offline GPU; do not promise an unimplemented adapter is available. Preserve drafts when unavailable.

## Uncertainty and proposals

Keep durable request fences and exact-scope closed-parent continuation. Freeze the selected context/revision/target/parent before dispatch. Reconnect or an editor change must not rebuild an uncertain request from new inputs or mint a new UUID. A duplicate admitted request is not cached success. Any recovery API requires its own scoped contract; do not fabricate one.

Initial advice is text under the existing contract. Future structured proposals, additional media and tools remain deferred. Revision-checked Apply, execution and generation qualification are separate operations. Model output does not authorize commands, paths or edits. Agent neither writes the Studio draft directly nor owns generation jobs/assets or Runtime scheduling.

## Review and later acceptance

The Intelligence-first task must define exact source removals and a functioning non-MCP contract, preserving principal/continuation isolation, revocation, prompt trust, context bounds, full-context export refusal, identity matching, truthful availability, partial-output rejection, duplicate/unknown behavior and credential redaction. Test with fake providers first; PostgreSQL/provider/restart/two-user live checks are separate evidence.

The renewed #18 instruction authorizes the internal source cleanup and connections. No DB migration, Generation Controller, ComfyWorkFlow/reference-image expansion or live operation is included. Historical #15 sequencing does not override #18.
