# Agent execution boundary (#10)

`AgentSession` owns prompt/history, conversation persistence and lifecycle. `ExecutionClient` resolves model identity and executes bounded ordered messages. Preserve this transport-independent boundary when replacing the existing internal MCP adapter; future local Runtime/API/vendor adapters do not require MCP as their internal contract. They are target adapter classes, not claimed implemented by this document.

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

After documentation review, the separately authorized Intelligence task inventories and removes unnecessary internal MCP transport/discovery plumbing while preserving this boundary and a functioning retained path. Do not delete model/provenance or export checks just because they reside near MCP code. Do not mix persona DB changes, new Studio features, Generation work or native-kernel redesign with transport cleanup. Documentation merge alone performs no code deletion or live migration.
