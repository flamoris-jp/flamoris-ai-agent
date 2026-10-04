# Legacy internal Intelligence MCP adapter

The internal Agent -> Intelligence MCP architecture is superseded by [AI #18](https://github.com/flamoris-jp/flamoris-ai/issues/18) and [Agent #38](https://github.com/flamoris-jp/flamoris-ai-agent/issues/38). The current adapter remains an as-built migration input until actual replacement/removal; this document does not change its configuration.

## Corrected target

```text
AI Agent -> non-MCP ExecutionClient / internal execution interface
              -> local Runtime / provider API / vendor runtime
```

The external Intelligence MCP facade is separate. Agent must not return through an external MCP entrance merely to reuse an adapter. Preserve a small internal interface instead of inventing a universal gateway or duplicating providers across callers.

## Current implementation reference

The existing implementation includes `AGENT_INTELLIGENCE_TRANSPORT=mcp`, MCP endpoint/target configuration, discovery/dispatch and result mapping. The current settings registry is `AGENT_INTELLIGENCE_TARGETS`, not a newly invented configuration name. The complete [pre-correction adapter contract](https://github.com/flamoris-jp/flamoris-ai-agent/blob/e949678efdee18219ceedbed650df097ed62a52f/docs/INTELLIGENCE_MCP.md) is pinned for operational and regression analysis, not active migration direction.

## Deletion-first preparation

Inventory exact source/tests, current callers and configuration. Identify transport mode/endpoint handling, MCP discovery/dispatch and translation needed only for the obsolete hop. Specify a functioning non-MCP execution contract and explicit unsupported-call behavior before removing a currently used path.

Keep `ExecutionClient` request/result semantics, model identity checks still required by the target, personality/conversation state, principal isolation, complete-context export consent, immutable snapshots, bounded context/output/time, redacted errors, provenance and durable request fences. A former MCP-specific code location does not make every safety check in it disposable.

Do not silently select direct mode when MCP fails, replay uncertain work or remove persistent records. Do not redesign persona DB, native Runtime, Generation or add provider/Agent features in this cleanup. Studio inbound MCP use is a separate internal hop to audit; inbound external Agent MCP compatibility is not the same as the outgoing dependency.

## Current authorization

Documentation review/fix/merge only, when explicitly requested. Work implementation and live migration need separate authorization. Existing deployments may still use the legacy adapter. Deprecated architecture is not evidence that the replacement exists or that current operators can remove its configuration.
