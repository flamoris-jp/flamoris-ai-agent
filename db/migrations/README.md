# Agent schema migrations

Apply additive SQL migrations in order after the initial `db/01_schema.sql`,
through the established schema-owner backup/migration procedure. Do not rewrite
the initial schema to upgrade a running database. Source acceptance does not mean
these migrations have been applied to a live database; no automatic migration or
grant provisioning is enabled.

| Order | Migration | Contract |
| --- | --- | --- |
| 002 | [002_principal_sessions.sql](002_principal_sessions.sql) | Operator-controlled delegation and immutable bounded principal sessions; [principal contract](../../docs/PRINCIPAL_SESSIONS.md) |
| 003 | [003_principal_retention.sql](003_principal_retention.sql) | Guarded owner-only retirement of expired bindings; preserves transcripts and request fences; [retention](../../docs/PRINCIPAL_RETENTION.md) |
| 004 | [004_assistant_settings.sql](004_assistant_settings.sql) | Model/settings grants and versioned personality state; [settings contract](../../docs/ASSISTANT_SETTINGS_V1.md) |
| 005 | [005_model_continuations.sql](005_model_continuations.sql) | Immutable same-principal model handoff lineage, source revocation and leaf-first retention; [continuation contract](../../docs/MODEL_CONTINUATION.md) |

Shared settings and continuation are opt-in. Review exact membership/delegation,
model and personality grants independently; a transport credential or migration
does not authorize a human. Match Studio's migration chain through
`20261005_12` for model switching and preserve backups/rollback fences.

The earlier pgvector/memory/relay filenames were planning examples, not shipped
migrations. pgvector remains outside the v0.1 schema contract.
