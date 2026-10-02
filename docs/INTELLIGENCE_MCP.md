# Approved Intelligence MCP execution

Owning issue: [#24](https://github.com/flamoris-jp/flamoris-ai-agent/issues/24).
This explicitly configured adapter consumes the current synchronous Intelligence
contract at commit `043b39b064fbedf9ed9a3e9e9eb57c6856efbb5c`. It preserves
AgentSession conversation/prompt/persistence authority. It creates no provider job,
Agent memory, runtime activation, tools, routing registry or automatic fallback.

## Configuration and authority

Default `AGENT_INTELLIGENCE_TRANSPORT=direct` keeps the temporary direct llama.cpp
console/MCP behavior. Explicit `mcp` requires `AGENT_INTELLIGENCE_MCP_ENDPOINT`
and JSON `AGENT_INTELLIGENCE_TARGET`. Unknown modes or incomplete configuration
fail closed; MCP failure never selects direct mode. All configuration is operator
controlled, never an ask argument or model-generated value. No credentials or
provider endpoints belong in the target mapping or conversation context.

Example target (replace aliases deliberately; this does not register a DB model):

```json
{"public_model_id":"gpt-oss-20b","provider_id":"llamacpp","db_model_name":"served-alias","db_provider":"llama.cpp","data_flow":"local_only"}
```

Required public ID/provider are exact Intelligence discovery pins. DB identity is
an explicit approved translation; public aliases are not assumed to equal served
model names. Existing runtime model validation compares this resolved identity
with the deployment's DB model reference before creating a conversation. Select
a new configured session/runtime model registration deliberately for any change;
never mutate the identity of a started turn.

Optional target fields: capability_id (text.generate, reasoning.generate or
code.generate; default text.generate), max_input_bytes (default/hard ceiling
65536), context_tokens (default 32768, 1024–1048576), max_output_tokens
(default 1024, 1–4096) and timeout_seconds (default/hard ceiling 120). The tighter
configured/discovered limit wins; an output budget above discovery is refused.

`data_flow` is required and currently accepts only `local_only`. The operator
must verify that the configured MCP's downstream provider keeps the entire
assembled request local, including personality and selected previous transcript.
The current Intelligence discovery does not attest locality. This is an explicit
deployment trust requirement, not an inference from an endpoint hostname. Remote
targets/export policy and per-principal target selection remain unsupported in
this slice. Configuring a remote URL alone never authorizes transcript export.

The current Intelligence HTTP listener has no application authentication and is
loopback-only. Use the actual approved private deployment endpoint; remote access
needs a separately reviewed authenticated boundary. No Hub configuration or live
service change is performed by this adapter. HTTP credentials embedded in URLs,
queries/fragments, redirects and environment proxies are rejected/disabled.

## Prompt, budget and result behavior

Resolution checks exact models.get/capabilities.get identities and synchronous
inference.execute support, then provider availability in system.health. These
checks run within 15 seconds without inference or runtime activation. Configuration
metadata plus provider reachability does not prove an alias is loaded; final
execution may still reject it. This resolution is not a Studio availability API.

The trusted first system message becomes instruction. Previous transcript and
current user/assistant history become a JSON agent_messages_v1 input envelope;
their role labels/content remain untrusted data. Additional system messages are
refused. No transcript data is promoted to trusted instruction. The adapter sends
one synchronous inference.execute, with no hidden tool/prompt/provider selection.

Validation covers input envelope/policy serialization overhead, the existing 64 KiB
combined limit, the tighter approved byte limit, Intelligence's conservative
bytes+512+output_tokens context heuristic, and a 128 KiB serialized request ceiling
(including JSON escaping). AgentSession validates startup context before
conversation creation and the assembled question before user persistence. No
truncation silently changes meaning. Model/provider validation still occurs in DB.

The execution deadline covers MCP initialization/dispatch/response/cleanup and
is at most 120 seconds. Each call owns/closes its SDK task groups in its own scope;
no SDK cancel scope survives into shielded Agent cleanup. Incremental response
transport has a 1 MiB ceiling, rejects compressed representations and prevents
SDK same-origin redirect replay. No inference POST is retried. Cursor-free SDK
observation/resumption does not grant permission for another inference attempt.

Only matching public provider/model/capability results with a valid execution UUID,
bounded nonblank text, consistent optional usage and finish_reason=stop succeed.
Length-terminated output returns incomplete_output, preserving an admitted user
turn/duplicate fence while omitting assistant-success persistence. Empty or invalid
output is refused. Correlation UUID is provenance, never an upstream job/recovery API.

DB provenance retains the approved runtime identity. MCP responses use validated
public model/provider IDs plus execution correlation, avoiding private DB aliases.
Adapter-scoped SDK logs redact transport messages/exception details; fixed error
codes cross the Agent boundary. Do not enable external provider/wire logging of
private prompts. Cancellation/disconnect cannot prove remote work stopped and
never trigger another attempt or a fabricated answer.

## Verification and remaining gates

Offline tests run actual in-process Streamable HTTP MCP negotiation/discovery and
execution with bounded fixture handlers. They cover mapping, transcript separation,
model/capability mismatch, unavailable provider, final serialization/context bounds,
partial/empty/oversized/malformed results, no replay, cancellation/cleanup, transport
limits/redirects/compression and SDK log privacy. Existing PostgreSQL isolation,
package/wheel/container gates remain required. No real provider smoke is implied.

Remaining #24 work: versioned Studio context envelope, complete classified remote
export policy/targets, Agent-owned scoped fresh availability, Studio account mapping
and two-principal/live Intelligence acceptance. Shared Studio assistance remains
disabled until those owning gates are met.
