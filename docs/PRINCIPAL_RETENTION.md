# Principal authorization binding retirement

Owning issue: [#30](https://github.com/flamoris-jp/flamoris-ai-agent/issues/30),
prerequisite of #18/#24. This is an explicit schema-owner operation. No automatic
eviction, refresh, new MCP tool or application-role deletion is introduced.

## What is retained

`chat.principal_sessions` contains short-lived authorization bindings, not the
Agent transcript or durable request fence. After expiry a binding cannot authorize
an ask, even while its row remains. Conversation metadata records the original
UUID/delegator/scope; participants/project/Agent references and all messages,
system context, runtime provenance and admitted request UUID fences remain in
their existing tables. Retirement never modifies or deletes those rows.

A new session still checks current exact grants and membership. A retired scoped
parent cannot be continued under a fresh session. Duplicate request fencing stays
Human/Agent/Project scoped across session changes. An insert trigger refuses any
new binding UUID already referenced in historical conversation metadata; a
historical binding cannot be re-established with changed authorization.

This is **not conversation or Memory retention/deletion**. Preserving an uncertain
closed attempt does not supply result recovery or imply that inference completed.
No transcript is read or exported by the retirement operation.

## Eligibility and bounds

Apply additive `db/migrations/003_principal_retention.sql` after 002 using the
established schema-owner path. It is repeatable, creates no grants and leaves
principal/expiry immutability unchanged. The migration adds a conversation
metadata index and guarded invoker functions/triggers; review index-build cost on
an existing database using the normal backup/migration procedure.

Retirement requires all of the following:

- Binding expiry is at least one hour old. Revocation alone cannot shorten expiry
  or the grace period, and active bindings cannot be removed.
- Every referencing conversation has exactly `status=closed`, a non-null
  `ended_at` at least one hour old, and no unfinished/recent associated
  conversation session or runtime instance.
- The candidate binding row can be locked immediately; active row locks are
  skipped. Open/unknown/inconsistent lifecycle records remain explicit blockers.

Each batch accepts an exact SQL integer 1–128 (default 32) and returns the count
retired. It uses the same advisory namespace lock as session publication and
refuses a busy namespace instead of waiting. The before-delete trigger checks the
same eligibility even for direct owner DELETE. Authorization admission already
locks and validates the binding row; after expiry new admission is impossible.
No binding, grant or inferred lifecycle is altered to make a candidate eligible.

Only the schema owner can execute `chat.retire_principal_sessions(integer)`.
PUBLIC and `flamoris_ai_app` execution are revoked; the runtime also lacks DELETE.
Invoker functions do not acquire a privileged role. The schema owner remains a
trusted database operator; do not grant that identity to the running service.

## Operator procedure

Use the existing private administrative connection. Do not put connection strings,
passwords, UUIDs or private principal keys in public reports. First inspect only
aggregate counts; this query performs no writes:

```sql
SELECT count(*) AS retained,
       count(*) FILTER (WHERE chat.principal_session_retirable(id)) AS eligible
FROM chat.principal_sessions;
```

After inspecting the current state, a reviewed maintenance run can perform one
bounded batch as the schema owner. Use the normal operations scheduler only when
explicitly configured by the operator; requests never schedule maintenance.

```sql
BEGIN;
SET LOCAL ROLE flamoris_ai_owner;
SET LOCAL statement_timeout = '5s';
SET LOCAL lock_timeout = '2s';
SELECT chat.retire_principal_sessions(32);
COMMIT;
```

On timeout/busy/error, rollback the transaction and inspect before a later explicit
run. Do not retry infinitely. A count of zero can mean grace, open/inconsistent
history or a row lock, rather than a defect. Do not manually mark an uncertain
conversation closed, clear its history or reset request IDs to recover capacity.
Retention does not restore revoked permissions or revive a parent session.

At most 128 retained authorization bindings globally / 32 per delegator still
govern publication. Operators must configure and observe an appropriate cadence
for their usage; database cleanup is not automatically enabled by this migration.
If unfinished history prevents retirement, admission stays fail-closed at capacity
until the owning lifecycle issue is resolved. Conversation growth has its separate
future retention policy; this change does not bound or delete durable user data.

## Verification and deployment limits

Disposable PostgreSQL tests apply the migration twice, reject runtime-role
execution/deletion, protect active/grace/open/unknown/recent runtime history, skip
held admission locks, refuse a busy namespace, recover bounded capacity and prove
that historical context/messages/provenance and duplicate fencing survive. A
historical UUID cannot be reinserted; another fresh session cannot read its parent.
These tests use synthetic data, not a live database or paid inference.

No live migration or retirement is executed by this delivery. Actual operator
maintenance configuration, deployed two-principal acceptance and Studio account
mapping remain separate integration checks.
