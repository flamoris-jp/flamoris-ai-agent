# AGENTS.md

This repository owns optional persistent Agent identity/personality, conversation/session state and memory/context policy. Read README.md, docs/EXECUTION_CONTRACT.md, docs/INTELLIGENCE_MCP.md, docs/ASSISTANT_SETTINGS_V1.md, CONTRIBUTING.md, SECURITY.md, [AI #18](https://github.com/flamoris-jp/flamoris-ai/issues/18) and [Agent #38](https://github.com/flamoris-jp/flamoris-ai-agent/issues/38).

## Current authorization

Review/fix documentation and merge it only with explicit user permission. This pass does not start Work implementation, source deletion, migrations, configuration changes, provider calls or deployment. Intelligence cleanup is the next priority; Controller implementation and Generation/reference-image work stay held.

## Target versus as-built

Agent uses a narrow transport-independent ExecutionClient/internal execution contract. Target adapters may call local Runtime, a provider API or vendor runtime without internal MCP. The existing MCP execution adapter/configuration still exists until a separately reviewed replacement/removal; document it truthfully, not as already migrated.

Do not introduce unimplemented configuration names. Current `AGENT_INTELLIGENCE_TARGETS` is not renamed by documentation. Do not tell operators to disable a setting required by the current package or enable an unimplemented replacement. Keep old runbook facts under an explicit as-built/rollout-hold label.

Distinguish inbound external Agent MCP from outgoing Agent-to-Intelligence MCP and Studio's internal inbound use. Internal FLAMORIS components must not depend on MCP in the target. External MCP tools are not deleted merely because an internal client is removed.

## Ownership

Personality, conversation, principal/session, memory/knowledge policy, Agent-specific prompts, explicitly granted tools and Agent provenance belong here. Raw inference and generation do not require Agent. Provider model/runtime state, generation jobs/inputs/assets, product documents and GPU/systemd lifecycle remain with their respective owners.

The latest #18 decision supersedes old instructions to use Intelligence MCP/Generation MCP as Agent's internal service boundary. Keep replaceability without hard-coding providers into persona or duplicating adapters into every caller. Do not create a universal gateway service or new Intelligence Controller without a separate justified decision.

Use ExecuteFlow for Runtime inference flow, preserve ExecutionPlan for its compiled form, and use ComfyWorkFlow for ComfyUI graph/JSON. Current literal source/wire/config identifiers and historical records retain their true names until a reviewed migration.

## Cleanup constraints

Before implementation, inventory exact source/tests/configuration, actual callers, retained behavior and unsupported-call handling. Remove only MCP-specific plumbing made unnecessary by a specified working non-MCP route. Preserve model identity validation, capabilities actually required by the target, full-context export policy and request fences; do not delete checks merely because they were formerly reached through MCP.

Do not mix transport removal with persona DB redesign, new UI/features, Generation cleanup or native Runtime changes. Source removal does not authorize deletion of conversations, revisions, grants, assets, evidence or unresolved work. Do not silently fallback to a retired path or replay uncertain requests.

## Security and state

One authority per state domain. Memory is user-impacting durable state, not an incidental cache: retention, provenance, update/delete, visibility and export rules must be explicit. Provider caches are not Agent memory.

Retrieved knowledge, drafts, prior messages, model output and tool results are untrusted data. They must not replace trusted personality/system policy or grant capabilities. Filesystem/network/product-editing and credential-bearing actions require bounded explicit permission; model-generated paths, URLs and commands are not authority.

Preserve immutable principal/session identity, membership/delegation checks, conversation ownership, persona/model snapshots, revocation semantics, safe provenance, bounded contexts, redacted errors and durable duplicate handling. Authorization covers the complete remote request, including selected history/personality/attachments. Local failure is not remote consent.

Never commit/log secrets, keys, passwords, cookies, private topology or unnecessary user data. Credentials and transport settings do not belong in personality, prompts or memory. No hidden destructive actions or unbounded retry.

## History, tests and review

Keep imported records until an explicit migration/removal decision. Do not rewrite historical evidence to match current architecture. `.env.example` is documentation; real `.env` stays untracked. Historical Ollama coupling does not override the corrected target.

Use focused deterministic tests and fake providers/DB fixtures. Normal CI needs no GPU, weights, paid API or private persona. Test rejection paths, two-principal isolation, model/provenance mismatch, remote refusal, uncertainty and persistence. Actual PostgreSQL/provider/restart acceptance is separate.

Review resulting prose and code literals after edits; keyword replacement alone is insufficient. Keep current status and future direction distinct. Merge only with authorization and report actual checks, not assumed CI. Generic infrastructure stays in Commons or dedicated packages; products keep their own revision/concurrency/undo/permission model.

## License and support

Code/docs are Apache-2.0 unless otherwise stated. Third-party source, models, weights, datasets, prompts, fonts and media require compatible documented terms. FLAMORIS has no guaranteed individual support; repository documents, Issues, tests, logs and source are primary references.
