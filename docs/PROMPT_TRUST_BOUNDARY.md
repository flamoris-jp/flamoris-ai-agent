# Previous-conversation trust boundary

The Agent's local personality/context files and fixed rules form the system
message. Retrieved previous conversation text is never interpolated into that
governing message.

When previous messages exist, the runtime adds one separate `user` message
containing a JSON object with `kind: untrusted_previous_conversation` and the
retrieved conversation. Historical role, sender, timestamps, and conversation ID
are retained as JSON data. A historical `system` role stays a string in that
data; it cannot create an API-level system message. JSON serialization escapes
quotes and newlines rather than relying on user-controlled delimiters.

Fixed system rules explicitly describe the JSON as untrusted reference data,
not current instructions, unresolved tasks, or authoritative FLAMORIS knowledge.
The current conversation follows that reference message in its original roles.
The normal current-history window still applies; no synthetic message is added
when there is no previous conversation.

PostgreSQL still stores the previous conversation under `system_context` for
provenance. That JSONB column name is historical: its previous-conversation
member is data, not policy. The stored `system_prompt` now contains only the
governing prompt. Schema, identity, retrieval scope, and message writes are unchanged.

Tests verify the payload boundary, author/role preservation, and adversarial
history handling. They do not claim that prompt formatting can guarantee a model
will never follow malicious text. Future tools must enforce capabilities outside
the model, independently of this prompt boundary.
