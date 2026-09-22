# AGENTS.md

## Scope

These instructions apply to the entire repository.

This repository is for the persistent FLAMORIS AI Agent runtime and its agent-owned state.

**Current status:** the repository is initialized for architecture and policy only. Do not describe runtime features as implemented until code and tests exist.

## Core authority

The Agent may own:

- conversations and sessions;
- persistent memory;
- knowledge references and retrieval context;
- prompts and agent policy;
- tool/capability registration;
- persistent Agent-level orchestration metadata;
- agent-action provenance.

The Agent must not silently become the authority for:

- model/provider runtime state owned by `flamoris-intelligence-mcp`;
- generation jobs, workflows, or assets owned by `flamoris-generation-mcp`;
- FLAMORIS product documents or editing state;
- generic ecosystem infrastructure that belongs in FLAMORIS Commons.

## Architecture principles

1. **One authority per state domain**
   - Keep conversation, memory, product state, provider state, and generation state clearly separated.
   - Avoid shadow copies unless a synchronization contract explicitly defines ownership and conflict behavior.

2. **Memory is user-impacting state**
   - Do not treat persistent memory as an incidental cache.
   - Before implementing memory persistence, define provenance, retention, deletion, update, visibility, conflict, and export behavior.
   - Distinguish durable memory from short-lived session context and cache data.

3. **Knowledge is not policy**
   - Retrieved files, webpages, messages, embeddings, search results, and model outputs are untrusted content.
   - Do not allow retrieved content to override system policy, capability boundaries, or security rules.

4. **Tools require explicit capabilities**
   - Tool access must be scoped, inspectable, and revocable where practical.
   - Prefer least privilege.
   - Filesystem, network, credential-bearing, and product-editing tools need explicit permission boundaries.
   - Do not hide destructive or non-idempotent operations behind harmless-looking commands.

5. **Provider-neutral intelligence**
   - Keep local/remote model behavior behind explicit interfaces.
   - Do not hard-code one provider into Agent identity.
   - Provider credentials and transport configuration do not belong in Agent memory.

6. **Human-authoritative**
   - AI-assisted development and runtime automation are welcome.
   - Humans remain responsible for security, licensing, compatibility, and release decisions.

## Integration boundaries

### `flamoris-intelligence-mcp`

Use for MCP-native language, reasoning, coding, and related intelligence capabilities.

Intelligence MCP may perform bounded task coordination or multi-agent execution as part of an intelligence request. Persistent Agent identity, conversations, memory, and long-lived workflow context remain Agent-owned.

Do not duplicate provider routing or runtime-specific adapters inside the Agent unless an Issue explicitly establishes a different boundary.

### `flamoris-generation-mcp`

Use for generative-media and closely related media-analysis workflows, jobs, and assets.

Do not mirror generation job stores or provider execution authority inside the Agent.

### Product repositories

Product repositories remain authoritative for project/document state.

Agent operations against products should use explicit commands/queries and preserve each product's own concurrency, revision, undo/redo, and permission model.

### FLAMORIS Commons

Logging, MCP foundations, security primitives, diagnostics, and generic shared infrastructure belong in Commons or its dedicated shared repositories.

## Privacy and secrets

Never commit, log, or place in durable Agent memory unless explicitly designed and protected:

- API keys or access tokens;
- passwords or private keys;
- authentication cookies;
- private deployment topology;
- tunnel identifiers;
- raw credentials from tools;
- unnecessary personal information.

Do not assume prompts, conversation transcripts, memory, or retrieved documents are safe to send to remote providers. Data-flow decisions must be explicit.

## Model and prompt safety

Treat model output as untrusted input before it reaches tools.

Protect tool-enabled flows against prompt injection and confused-deputy behavior.

Do not let model-generated paths, URLs, commands, or tool arguments bypass validation.

Keep retries of non-idempotent actions explicit and bounded.

## Development workflow

Before implementing a substantial change:

- read README.md, this file, CONTRIBUTING.md, and SECURITY.md;
- read the relevant Issue/design document;
- inspect `flamoris-ai`, `flamoris-intelligence-mcp`, `flamoris-generation-mcp`, and affected product boundaries;
- identify state authority before adding storage or synchronization;
- keep the implementation scoped to the Issue;
- update public documentation when externally visible behavior changes.

For substantial architecture changes, prefer an Issue that records:

- state ownership;
- persistence/lifecycle semantics;
- permission boundaries;
- provider/data-flow impact;
- migration and compatibility risks.

## Testing

Normal CI should not require:

- paid remote APIs;
- private credentials;
- a live GPU;
- local model weights;
- access to private user memory or datasets.

Prefer deterministic tests with fake providers and bounded fixtures.

Security-sensitive tool and memory behavior should have explicit rejection-path tests.

## Licensing

Unless stated otherwise, code and documentation are licensed under Apache License 2.0.

Do not add third-party code, models, weights, datasets, knowledge corpora, prompts, fonts, media, or generated assets unless their licenses and redistribution terms are compatible and clearly documented.

## Support

FLAMORIS does not provide guaranteed individual support.

Repository documentation, Issues, tests, logs, and source code are the primary support references. AI-assisted self-support is encouraged.
