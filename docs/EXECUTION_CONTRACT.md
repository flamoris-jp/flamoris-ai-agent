# Agent execution boundary (#10)

`AgentSession` owns prompt/history, conversation persistence and lifecycle. `ExecutionClient` resolves model identity and executes bounded ordered messages. Approved targets use the shared non-MCP provider library, preserving original message roles. See [the implemented internal contract](INTERNAL_EXECUTION.md); future native Runtime adapters remain separately scoped.

`ModelIdentity(provider, model)` is checked against the registered runtime row. `ExecutionRequest` contains ordered system/user/assistant messages; results must match the selected identity before assistant persistence. Previous conversation material stays untrusted JSON data, not trusted system instruction.

Existing boundary limits: 64 KiB combined UTF-8 context, 16 KiB user text, 64 KiB output, 1 MiB provider response, 128 messages, 4096 output tokens and 120-second whole-request deadline. The direct model discovery deadline is 10 seconds. A target adapter's tighter limits still apply. No redirects, environment proxies, implicit retries, provider fallback or runtime activation. Cancellation closes local work but cannot prove remote inference stopped. Errors are fixed codes, not provider bodies, credentials or private URLs.

## Durable effects

- Validate startup model/configuration before transactional instance/conversation creation; roll both back on failure.
- Commit the user message before inference. Failure/cancellation may leave an admitted user turn unanswered; do not replay it silently.
- Persist the assistant before exposing it as a successful local/returned answer. Ambiguous or failed persistence poisons the session: close it and inspect state rather than retrying the turn.
- Close session/conversation/instance transactionally and always close the connection. DB outage or process kill may prevent lifecycle timestamps; report uncertainty rather than fabricated cleanup.
- Trim in-memory history separately from PostgreSQL's durable transcripts.

The console's single-user latest-conversation lookup must not become an unscoped remote lookup. Fixed/shared MCP surfaces retain their own principal, continuation and durable duplicate contracts. This correction changes no schema or imported historical record.

## Current correction scope

The earlier #10/#11/#13 implementation authorization and #2 acceptance are historical records, not permission to restart work now. Current authority is [AI #18](https://github.com/flamoris-jp/flamoris-ai/issues/18) / [Agent #38](https://github.com/flamoris-jp/flamoris-ai-agent/issues/38).

The renewed user authorization removes outbound MCP transport/discovery/translation while retaining this working boundary, model/provenance checks, context/export policy and durable state. Internal HTTP uses the same domain service as external MCP. No persona DB redesign, new Generation capability, native-kernel change or live migration is part of the cleanup.
