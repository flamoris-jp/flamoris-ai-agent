# Model switching within a conversation

Agent #42 adds opt-in internal HTTP `POST /api/v1/sessions/continue` with
`session_id`, `request_id`, `model_id`, and `remote_consent`. It is available
only with shared principals and settings enabled; the external MCP catalog is
unchanged. Apply source migration 005 after 002–004 during a separately approved
rollout. This PR does not apply it to a live database.

The current authorized session must be valid. The handoff creates a new immutable
principal/model snapshot with the same human, Agent and project, records its
parent, and revokes admission through the old session atomically. A UUID derived
from the authenticated delegator, source session and request ID makes retry after
a lost acknowledgement return the same committed handoff. Changing its target
fails. No inference is performed by a handoff.

An active, unfinished or uncertain source turn prevents switching. Current
membership/model grants and configuration are checked again. Moving to an API
model requires explicit consent for personality, historical messages and attached
drafts as part of the complete exported context. Local failure never supplies it.

Only recorded same-principal ancestry permits reading an old conversation.
Unrelated sessions, another user and another delegator cannot inherit it. The
original personality revision and message provenance remain unchanged; the new
turn records its selected model separately. The selected history is a rolling
window of at most 12 messages and 64 KiB including historical draft context.
Historical content remains untrusted user data. Full transcripts stay persisted;
this does not promise unlimited model context or automatic summarization.

Sessions retain the existing 15-minute authorization lifetime and namespace
capacity (128 total, 32 per delegator); a lineage is bounded to 31 handoffs.
Owner retirement visits eligible expired leaves first and cannot delete an
ancestor while a child is retained. Existing conversations, provenance and
uncertain request fences are never erased by handoff. Shutdown drains an admitted
handoff transaction. Rollback requires preserving migration 005 and its lineage
records; do not delete them to force old-package compatibility.
