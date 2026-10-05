# Scoped Image context and ask availability

Owning issue: [#24](https://github.com/flamoris-jp/flamoris-ai-agent/issues/24).
This extends only the explicitly authenticated shared HTTP catalog. Default stdio,
fixed HTTP ask/health, console history and direct execution stay compatible.
Studio's authenticated account/principal mapping and deployed catalog parity
remain necessary; this change does not activate a shared Studio assistant.

## Context revision 1

`ask_scoped.request.context` is optional. Without it the existing scoped request
shape/behavior remains. When attached it has exactly these fields:

| Field | Contract |
| --- | --- |
| revision | Exact integer 1; booleans/coercions refused |
| category / operation | image / image.generate only |
| product_context_id | Canonical opaque Studio context UUID; not a retrieval grant |
| draft_revision | Strict integer 1–2147483647 |
| draft | Whitelisted editable Image scalar data below |
| workflow | Optional exact id/version/digest plus image profile revision 1 |
| assets | At most 8 unique safe Image metadata descriptors |

Draft fields: positive_prompt/negative_prompt (strings, each max 16384 characters),
width/height (optional strict integers 64–4096 in multiples of 8), steps (1–150),
cfg (finite 0–100), denoise (finite 0–1), seed (strict 0–18446744073709551615).
The **entire serialized UTF-8 envelope**, including field names/metadata/escaping,
is limited to 16 KiB; per-field character ceilings do not replace that aggregate
bound. Additional fields, paths/URLs, executable graph, policy, model selection,
tool commands or binary attachments are refused. No generic schema-driven context
for unreviewed Music/Speech/Video profiles is introduced.

The retained `workflow` context DTO contains safe id (max 128 ASCII identifier characters), positive
integer version, lowercase SHA-256 digest, profile=image/profile_revision=1.
Asset descriptors contain canonical Studio UUID, sanitized display_name (max 100
ASCII letters/digits/underscore/dot/hyphen), media_kind=image, exact PNG/JPEG/WebP
MIME and optional size_bytes (0–1 GiB). These identifiers never cause an Agent file
fetch. Studio must reauthorize every selected asset and selected Image template, construct
safe metadata itself and bind the product/draft revision before dispatch. Agent
validates the envelope under the authenticated delegator/session but does not
establish Studio product ownership from its fields.

AgentSession immediately freezes a detached serialized snapshot. It stores that
snapshot in the new conversation's context, alongside configured Agent sections
and any authorized closed-parent transcript. The prompt passes it as a user data
message with kind=untrusted_studio_context, never system instruction or tool
authority. Advice neither applies edits nor submits Generation work. Retention
follows existing Agent conversation retention; no long-term Memory is added.

The complete personality + previous transcript + draft envelope + question and
serialization overhead must fit Agent and approved Intelligence budgets. Startup
and question admission reject overflow before their respective writes/dispatch;
no truncation or background attachment retrieval. Uncertain calls retain their
original snapshot and request UUID and never reassemble/replay a newer draft.
There is still no request recovery/status or cached-answer API.

Context-bearing execution requires an explicitly approved direct target from
[INTERNAL_EXECUTION.md](INTERNAL_EXECUTION.md). The unclassified console path
refuses context_unavailable before dispatch. Remote settings targets still require
current grants and complete-context consent; legacy/local-only transcript export
remains forbidden. The outgoing MCP mode is retired and never used as fallback.

## ask_availability

Shared catalog is now exactly `health`, `sessions.open`, `ask_scoped`,
`ask_availability`. Review exact Hub catalog/schema parity before enabling it.
The new read-only/idempotent tool takes `request: {session_id}` and no other fields.
It first verifies current caller ownership, expiry/revocation and exact grants.
Unknown/forbidden sessions return only a fixed principal error.

For an authorized session it returns ok, available, state, reason, observed_at,
expires_at, principal_revision=1, context_revisions=[1], proposal_revisions=[].
State is ready, busy, offline, unavailable or unknown. Public reasons are fixed;
no principal/model topology or active request identity is returned. Observations
expire 5 seconds after the bounded probe completes; they never reserve admission
or guarantee future success. Recheck current authorization/limits on every ask.

One prerequisite probe per process, bounded to 15 seconds, checks explicit direct
configuration, selected Agent personality bounds, exact served model discovery,
provider reachability, current principal/runtime DB references
and approved model identity. Authorization is checked again after the probe.
If an ask starts during the probe, its result is busy; shutdown/revocation cannot
produce ready. No conversation/instance/message writes, private transcript reads,
inference, paid request, model switch, GPU activation or automatic fallback occur.

Direct mode remains dependencies_unknown for this new shared-assistant query;
health(alive, dependencies=not_checked) never implies ready. An explicit approved
A direct target whose provider is unreachable reports offline. Bad/unknown prerequisites
are unavailable/unknown. Current Intelligence configuration discovery/provider
health do not attest the exact alias is loaded; execution performs its own
validation and may reject it. Live model qualification remains a separate gate.
An API-ready Agent is not claimed: remote data-flow policy/adapters are deferred.

## Verification

Tests exercise actual Streamable HTTP schema negotiation and calls; inline nested
DTO schemas avoid SDK $defs-root ambiguity. Tests cover invalid revisions/fields,
aggregate Unicode bounds, immutable context after mutation, injection as data,
combined final budget, explicit direct-mode refusal, authorized fresh availability,
unknown/offline/configuration failure, revocation during probing, competing probes,
cancellation and no inference/lifecycle writes. Existing PostgreSQL isolation and
package/wheel/container gates still apply. No production two-user acceptance is
implied. Studio mapping/UI, operator retention configuration, remote export, proposals,
additional media contexts and deployment acceptance remain open.
The bounded owner-only binding retirement implementation is specified in
[PRINCIPAL_RETENTION.md](PRINCIPAL_RETENTION.md); it is not transcript deletion.
