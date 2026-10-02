# Persisted principal session foundation

Owning issue: [#18](https://github.com/flamoris-jp/flamoris-ai-agent/issues/18).
This first delivery is internal. Existing fixed-principal `health`/`ask`, console,
HTTP authentication and Intelligence execution remain compatible. Shared transport
session tools and Studio account mappings are not activated by these classes.

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
capacity. Set `TEST_AGENT_DATABASE_URL` only to the disposable `agent_test` database
to run those tests locally. They do not use live Agent data, GPU or paid inference.

Remaining #18 slices: authenticated transport delegation/session tools, bounded
shared ask dispatch and full parent/duplicate/concurrent-principal protocol tests;
explicit Studio-account delegation mapping; session retention and deployed
two-principal acceptance. #24 context/availability integration follows those gates.
