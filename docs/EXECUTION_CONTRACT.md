# Agent execution boundary (#10)

The console and future MCP surface use one `AgentSession`. It owns prompt/history,
conversation persistence and lifecycle; an `ExecutionClient` only resolves model
identity and executes bounded messages. The temporary llama.cpp adapter implements
this interface. No runtime activation, provider fallback or implicit retries.

`ModelIdentity(provider, model)` is validated against the existing runtime row.
Each `ExecutionRequest` carries ordered system/user/assistant messages; the result
returns text plus the same identity. A mismatch fails before assistant persistence.
Previous conversations remain untrusted JSON data, never system instructions.

Limits: 64 KiB combined UTF-8 context, 16 KiB user text, 64 KiB output, 1 MiB
provider response, 128 messages, 4096 output tokens, 120-second whole-request
deadline. Model discovery has a 10-second deadline. Redirects, environment proxies
and retries are disabled. Cancellation closes the HTTP request; it cannot promise
the remote model has stopped computing. Errors expose fixed codes, not raw URLs,
provider bodies or prompts. Operators alone configure the endpoint and model.

## Durable effects

- Startup validates model/configuration before creating state. Instance and
  conversation creation is transactional; errors roll back both.
- A user message is committed before inference. Provider failure/cancellation can
  leave that user turn without an answer. No silent replay or inference retry.
- Assistant persistence must succeed before the answer enters local history or is
  returned. A failed/ambiguous persistence write poisons the session: close it and
  inspect the DB; do not retry the turn automatically.
- Shutdown closes session/conversation/instance transactionally and always closes
  the connection. A DB outage may prevent end timestamps; errors are reported,
  never represented as successful cleanup. Process kill cannot guarantee cleanup.
- History in memory is trimmed; durable transcripts are retained in PostgreSQL.

The console preserves single-user latest-conversation lookup. A future remotely
accessible MCP must NOT reuse that unscoped lookup; caller/conversation scope and
duplicate handling belong to #11. No schema or imported historical record changes.

User authorization on 2026-09-26 permits offline #10 → #11 → #13 implementation
before live acceptance. #2 remains the real GPT-OSS/PostgreSQL/restart gate.
