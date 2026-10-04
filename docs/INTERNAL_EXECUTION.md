# Internal Agent HTTP and direct Intelligence execution

The internal route is Studio backend -> Agent HTTP `/api/v1` -> `ExecutionClient`
-> the shared `flamoris_intelligence` provider library. Ordered system/user/assistant
messages reach the selected provider without MCP negotiation or transcript flattening.
The same Agent domain service, principal authority, conversation store and request
fences also serve the retained external MCP adapter at `/mcp`. Transport adapters
do not create independent stores or grant a principal access.

## Internal HTTP contract

All routes except the process-only `/healthz` require the existing operator
`AGENT_MCP_TOKEN`, exact allowed Host, no Origin and no Content-Encoding. The token
name remains compatible; it authenticates the backend, not the human. Shared mode
requires `AGENT_HTTP_DELEGATOR_KEY` and the existing DB delegation/membership grants.
Request JSON is the operation's `request` object directly, without a JSON-RPC or
MCP wrapper. Bodies are bounded to 128 KiB; duplicate keys, nonfinite numbers,
invalid encodings and malformed objects fail before service dispatch.

| Method and path | Availability / domain operation |
| --- | --- |
| GET `/api/v1/capabilities` | `{ok: true, api_version: 1, operations: [...]}`; no dependency activation |
| GET `/api/v1/health` | Existing safe service health; liveness is not model/DB readiness |
| POST `/api/v1/ask` | Fixed-principal mode only |
| POST `/api/v1/sessions/open` | Shared `sessions.open` |
| POST `/api/v1/ask-scoped` | Shared `ask_scoped` |
| POST `/api/v1/ask-availability` | Shared read-only availability probe |
| POST `/api/v1/models/allowed` | Shared opt-in settings model grants |
| POST `/api/v1/personality/get`, `/api/v1/personality/history`, `/api/v1/personality/save` | Shared opt-in personality operations |

Operations appear only in the catalog for their enabled mode. Responses retain
the existing domain DTO, including fixed `{ok: false, error: {code: ...}}`
failures, principal/session/request identity and safe public provenance. Existing
request UUIDs, duplicate/uncertain handling, revocation checks, consent, personality
head locks and continuation compatibility are unchanged. This adds no DB schema
or import and does not convert a service token into a user identity.

## Execution configuration

The base shared distribution is pinned to the approved Intelligence commit in
`pyproject.toml` and the Docker build. Only its non-MCP namespace is imported by
the execution adapters; the SDK remains installed for the separate external Agent
surface. Vendor I/O, model probes, response normalization, bounds and private HTTP
diagnostics are shared rather than copied into Agent.

`AGENT_INTELLIGENCE_TARGET` selects the existing bounded operator-approved local
target; the settings registry remains `AGENT_INTELLIGENCE_TARGETS`. Target public
IDs map to the registered immutable DB provider/model identity. `capability_id`
retains its fixed `text.generate` value. `INTELLIGENCE_BASE_URL` is the trusted
llama.cpp provider base URL, not an MCP endpoint. Exact alias discovery precedes
conversation creation; returned model identity is checked before assistant storage.

Transport defaults to `direct`. `AGENT_INTELLIGENCE_TRANSPORT=mcp`, unknown modes,
or any nonempty `AGENT_INTELLIGENCE_MCP_ENDPOINT` fail explicitly. The retired
outbound client/discovery/schema/translation module was deleted. There is no
fallback to it, another provider or a remote API.

The historical unclassified console configuration still uses direct llama.cpp
with exact model discovery. Scoped Studio context requires an approved target.
OpenAI is available only through an explicitly selected granted settings session
with complete-context remote consent. Configure `FLAMORIS_INTELLIGENCE_OPENAI_API_KEY`,
the input/output USD-per-million estimates and `OPENAI_MAX_REQUEST_USD` under the
same prefix. Pricing and the per-request ceiling are operator inputs, not live
price claims. Remote default console/context targets are forbidden.

Changing execution configuration invalidates stored target digests; old sessions
are not silently retargeted. Existing conversations, model/personality identities,
revisions, grants and fences remain intact. Source cleanup does not migrate a live
deployment or drain its requests. Any operational cutover must preserve/reconcile
uncertain work, configure direct provider credentials separately and create a fresh
authorized principal session. No production operation is performed by this change.

## Evidence and limits

Fake-provider tests check ordered context, exact aliases, model/provenance mapping,
partial output, bounded bytes/context/usage, cancellation and no replay. Internal
HTTP tests exercise the real Agent service with the same transport authorization
and principal/session policies. PostgreSQL fixture, package and container checks
run in CI without GPUs, private personas, weights or paid inference. These checks
do not establish live model/DB/host readiness or physical shared-host capacity.

Native AI Runtime embedding remains a separate implemented Runtime contract; no
new Agent-to-native Runtime adapter is introduced. Generation Controller remains
unimplemented and is not a destination for the retired subsystem.
