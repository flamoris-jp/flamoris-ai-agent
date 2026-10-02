# migrations

FLAMORIS AI DBの将来migration置き場。

予定例:

```text
002_pgvector.sql
003_memory_retrieval.sql
004_relay_worker.sql
```

`002_principal_sessions.sql` adds explicit operator-controlled delegation grants
and immutable bounded principal sessions for #18. Apply through the established
schema-owner operations path before future shared-mode activation. It creates no
authorization grants automatically. See `docs/PRINCIPAL_SESSIONS.md`.

v0.1ではpgvectorをまだ有効化しない。

Schema変更時は既存の `01_schema.sql` を直接書き換えて運用するのではなく、
DB稼働開始後はmigration SQLを追加して履歴を残す。
