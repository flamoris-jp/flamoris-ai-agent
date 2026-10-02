# Persisted principal session foundation

Owning issue: [#18](https://github.com/flamoris-jp/flamoris-ai-agent/issues/18).
Existing fixed-principal `health`/`ask`, console and Intelligence execution remain
compatible. Shared HTTP is explicitly opt-in; Studio account mappings, retention
operations and deployment acceptance remain separate gates.

## Authenticated HTTP catalog

After migration and exact operator grants, `AGENT_HTTP_DELEGATOR_KEY` selects a
safe stable service caller (1–64 ASCII letters, digits, underscores or hyphens).
The authenticated private HTTP middleware binds that operator-selected identity
to the current request. Neither headers supplied as principal claims nor tool
arguments can replace it. Its Bearer token authenticates this delegator, not a
Human. This mode is suitable only for a trusted server that independently maps
its authenticated account to the allowed principal keys; do not expose the token
to browsers or users. Anyone holding the token can request any tuple explicitly
granted to that delegator.

With no delegator configured, the catalog remains `health`, `ask`. With one
configured, it is exactly `health`, `sessions.open`, `ask_scoped`,
`ask_availability`; legacy `ask`
is absent and has no fallback. Mixed service/transport modes fail at app creation.
stdio and console stay fixed-principal. Review exact Hub catalog parity before
enabling this catalog in a deployment; setting this variable changes discovery.

`sessions.open` takes `request: {human, agent, project}` with no other fields.
It returns `session_id`, UTC `expires_at` and `principal_revision: 1` on success.
`ask_scoped` takes the existing bounded ask request plus required `session_id`;
it accepts no identity/provider overrides. The session UUID is canonicalized and
revalidated for the authenticated caller before constructing a request-local
AgentSession. Its store and Agent context are captured from the frozen binding.
Success includes the session ID alongside existing conversation/request/answer
provenance. A missing caller, denied/expired/revoked binding or DB failure denies
dispatch; no fixed-principal conversation or inference is attempted.

All scoped asks share the existing one-active-request admission guard, cancellation
and cleanup behavior. This provides isolated logical sessions, not concurrent GPU
execution. `health` still reports dependencies `not_checked`; it cannot enable
Studio assistance. The separate scoped availability query and optional bounded
Image context are specified in [STUDIO_CONTEXT_V1.md](STUDIO_CONTEXT_V1.md).
No proposal/tool execution is advertised.

## Authority and lifecycle

`PrincipalSessions` accepts a delegator identity supplied by a trusted transport
boundary and untrusted requested human/Agent/Project keys. It resolves enabled
Humans/Agents, an active Project, exact Agent/Project membership and an enabled
operator-created `core.principal_grants` tuple. A service credential or arbitrary
session UUID never establishes that tuple. No request can create a grant.

The additive migration `db/migrations/002_principal_sessions.sql` preserves the
original schema/history. Run it as the established schema owner through the
existing private database operations process before enabling shared mode. The
migration creates no users, memberships or grants and changes no model binding.
The baseline application role's inherited core DML privileges are explicitly
revoked on the new grant table; the runtime can only read grants. The operator
must provision exact delegation tuples separately. Never grant all combinations
merely because an upstream service token is valid.

Sessions contain immutable resolved IDs, safe stable keys, delegator, expiry and
optional revocation. They last 900 seconds; the SQL constraint permits at most an
hour. A database trigger rejects principal/expiry/identity changes and revocation
reversal. Selecting another principal or Agent requires a new authorized session.
Keys and UUIDs are identifiers, not credentials, and no token is persisted.

Admission checks membership, grant, enabled state, active Project, session owner,
expiry and revocation again before conversation creation. Authorization linearizes
at that database read. A later grant/membership revocation blocks new requests;
an already admitted bounded text turn may drain under its frozen principal/model
and gain no new tools. Session revocation itself serializes with conversation
creation on the bound row. No runtime activation or inference is performed by
principal resolution.

## Conversation scope and compatibility

`MCPStore` can capture an explicit authorized binding and use its resolved
principal while keeping deployment-owned host/application/model references.
`load_agent_context(agent_key)` selects the bound Agent's private ordered sections
without changing environment/global state. Missing context never falls back to
another Agent. Existing calls without an explicit key retain their old behavior.

The durable request fence remains scoped to Human/Agent/Project across session
changes, so a fresh session cannot replay an existing admitted request UUID.
Scoped parents additionally require the same principal session. Fixed-principal
parents must have no scoped-session field; the old endpoint cannot read a new
shared-session conversation as legacy history. No latest-parent lookup is added.

## Finite retention

At most 128 bindings globally and 32 per delegator are retained, including expired
or revoked records. Publication serializes counts in PostgreSQL and refuses full
storage; it never evicts history or bindings potentially referenced by uncertain
requests. There is intentionally no automatic GC or refresh in this slice.
Reference-aware operator/session retention is a remaining shared-service gate,
not permission to delete conversation state or reset duplicate fences.

## Acceptance

Offline unit tests cover bounded keys, immutable identity, explicit context without
global mutation, missing bindings and revocation before persistence. CI additionally
uses a disposable PostgreSQL 16 database to apply the original schema and migration
twice, check exact delegation/other-caller rejection, two-principal restart,
each revocation gate, SQL immutability, grant-table runtime permissions and bounded
capacity. Real SQL parent selection rejects another Human, a different session
for the same Human and fixed-principal legacy access; duplicate request fencing
survives a new session while remaining isolated for a different Human. In-process
Streamable HTTP protocol tests cover authentication-context propagation/reset,
catalog shape, two request-local AgentSessions, denial before inference and the
shared admission/cancellation guard. These protocol tests use fake inference.
Set `TEST_AGENT_DATABASE_URL` only to the disposable `agent_test` database
to run those tests locally. They do not use live Agent data, GPU or paid inference.

Remaining #18 slices: explicit Studio-account delegation mapping;
session retention and deployed
two-principal acceptance. #24 context/availability integration follows those gates.
