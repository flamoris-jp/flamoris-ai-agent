# Bounded Agent MCP (#11)

This is a single-principal service, not a multi-user Agent. The trusted stdio
launcher/operator selects FLAMORIS_HUMAN_KEY, AGENT_KEY, PROJECT_KEY and immutable
runtime references. Tool inputs cannot change these identities or the provider.
HTTP is a separate authenticated deployment layer (#13). No automatic Hub setup.

Local tools are `health` and `ask`; a Hub namespace of `agent` produces
`agent.health` and `agent.ask`, not agent.agent.ask.

## ask

Input is one `request` object with exactly:
- `request_id`: caller-generated UUID; reuse when outcome is uncertain.
- `text`: nonblank UTF-8 text, at most 16 KiB.
- `previous_conversation_id`: optional UUID identifying an explicitly selected,
  closed MCP conversation belonging to the configured human/Agent/project.

Each ask creates a **new** conversation, runs one turn through AgentSession and
closes it. Continuation uses the selected previous transcript as untrusted JSON;
it does not reopen/append to the old conversation. No unscoped latest-history
lookup is used. This intentionally bounded first slice does not expose in-place
resumption or transcript CRUD. The response provides conversation_id, request_id,
text and model/provider provenance only after persistence and cleanup succeed.

The conversation UUID is derived from the immutable human/Agent/project IDs plus
request_id. Its existing primary key is the durable duplicate fence, across
processes/restarts. Creation and runtime registration are one transaction.
The request ID and parent reference are stored in conversation/message metadata.
Any existing conversation with the same derived UUID yields duplicate_request,
never another inference and never cached private text. A duplicate can represent
a previous failed, cancelled, or uncertain request; inspect it before issuing a
new ID. Records deleted outside this API remove the fence. UUID collisions fail
closed. This is at-most-one *admitted attempt*, not exactly-once completion.

Admission is one ask per process with no queue; busy calls fail immediately.
Separate conversations cannot race on a shared transcript because MCP only
reads closed parents and writes new conversations. Additional processes are NOT
a shared GPU reservation mechanism; deploy one process/worker.

Provider cancellation leaves a committed user message and closes the conversation;
no answer is fabricated. DB writes can have uncertain outcome after disconnect.
Never retry automatically. Existing schema and direct console semantics remain.
DB calls are synchronous with connection/statement/lock timeouts (5/5/2 seconds);
cancellation is delivered between these bounded sections. Inference has a
120-second whole-request deadline. Graceful shutdown cancels and drains active asks.

## health

Reports alive, busy, and dependencies=not_checked. It does not query private
transcripts, activate runtimes, or pretend that process liveness proves DB/model
readiness. A successful ask and the #2 acceptance checklist establish live evidence.

## Trust and limits

Only MCP-created, closed, exact-scope conversations may be selected as parents.
Their human participant must match and their stored scope metadata must agree.
Unknown/out-of-scope/open IDs all return conversation_unavailable. Caller IDs
are not authorization. Context text and metadata remain data, never policy.
Parent retrieval uses at most 12 messages, bounded text fields, and rejects
oversized context instead of silently truncating meaning.

Fixed error codes omit credentials, topology and prompts. No model-generated
tools/SQL/paths/URLs, remote fallback, memory CRUD or GPU management. Limits from
EXECUTION_CONTRACT.md apply; HTTP bodies in #13 are bounded to 128 KiB.
The SDK stdio decoder trusts the local launcher to bound transport frames; tool
input/context limits still apply after decoding. stdio stdout is protocol-only.
Operator-supplied personality files are trusted policy.

Offline protocol/DB fakes are not real PostgreSQL/GPT-OSS acceptance. Keep #2 open.
