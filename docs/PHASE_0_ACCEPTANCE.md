# Phase 0 deployment acceptance

This is the evidence checklist for [#2](https://github.com/flamoris-jp/flamoris-ai-agent/issues/2),
not a claim that the deployed system passed. Offline tests use fake providers and
DB connections. Server health alone cannot prove an Agent conversation was saved.

## Procedure

Follow [the runbook](PHASE_0_RUNBOOK.md) from the exact revision being tested.
Use the existing configured database and Agent identity. Do not recreate the
database, rerun the initial schema, or repoint an existing runtime model key.

1. Record the tested commit and package version. Verify the configured runtime's
   health and model list; resolve its actual served model ID.
2. Register the host/model as described by that revision's runbook and verify DB
   references. Confirm the existing Agent ID is preserved across model migration.
3. Start the console, send a harmless synthetic test message, and receive a real
   GPT-OSS response. Keep the transcript private.
4. Exit with `/bye`. Verify the conversation, user/assistant messages, and runtime
   instance in the existing database. Confirm their Agent/model linkage and the
   instance/session/conversation shutdown timestamps.
5. Restart. Verify the previous conversation is retrieved and usable as context,
   then exit cleanly again. Where #7 is included, check that previous text is data
   in `system_context` and does not appear in the governing `system_prompt`.
6. Record pass/fail per row below in #2. Do not post credentials, private endpoint
   addresses, transcripts, or unnecessary host/user details in the public Issue.

## Evidence template

Tested commit: `<commit>`

| Check | Result | Non-sensitive evidence |
|---|---|---|
| Runtime health and actual model resolution | Pending | |
| Existing Agent identity preserved | Pending | |
| Umeko starts and returns a real response | Pending | |
| Conversation and user/assistant messages saved | Pending | |
| Runtime instance references the correct model/Agent | Pending | |
| Clean exit closes session/conversation/instance | Pending | |
| Restart retrieves the previous conversation | Pending | |
| Previous context remains data (#7 revisions) | Pending | |
| No credentials/private context published | Pending | |

Only close #2 after all required live checks pass. If deployment access is not
available, keep this as a blocker rather than recording a fake-provider test as
runtime acceptance. Phase 1's owning Issue #10 consumes this gate.
