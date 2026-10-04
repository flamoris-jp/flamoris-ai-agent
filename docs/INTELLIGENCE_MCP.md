# Retired internal Intelligence MCP adapter

The outgoing Agent -> Intelligence MCP client was removed under
[AI #18](https://github.com/flamoris-jp/flamoris-ai/issues/18) and
[Agent #38](https://github.com/flamoris-jp/flamoris-ai-agent/issues/38).
The functioning replacement is the shared direct provider library behind
`ExecutionClient`; Studio uses the Agent internal HTTP API. Read
[INTERNAL_EXECUTION.md](INTERNAL_EXECUTION.md) for the current contract, exact
configuration and retained authorization/state obligations.

`AGENT_INTELLIGENCE_TRANSPORT=mcp` or a nonempty
`AGENT_INTELLIGENCE_MCP_ENDPOINT` now rejects rather than falling back. The
operator registry name remains `AGENT_INTELLIGENCE_TARGETS`. No conversations,
personality revisions, model identities, grants, snapshots or request fences were
deleted or migrated. Separate inbound external Agent MCP tools remain available.

The [historical adapter contract](https://github.com/flamoris-jp/flamoris-ai-agent/blob/e949678efdee18219ceedbed650df097ed62a52f/docs/INTELLIGENCE_MCP.md)
preserves the previous source/configuration and acceptance record for rollback
analysis. It is not a current installation or rollout instruction. Source cleanup
does not switch or reconcile a deployed service.
