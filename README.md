# FLAMORIS AI Agent

Persistent AI agent runtime for FLAMORIS.

**Status: the imported Umeko baseline is preserved. Phase 0 adds an optional GPT-OSS/llama.cpp console path; live deployment-environment acceptance is tracked separately.**

Part of the [FLAMORIS AI](https://github.com/flamoris-jp/flamoris-ai) family.

FLAMORIS AI Agent is intended to own long-lived agent-facing state and behavior: conversations, memory, knowledge access, prompts, tools, and orchestration toward intelligence and generation services.

It is not the model runtime itself, not the media-generation engine, and not the owner of FLAMORIS product documents.

## Imported baseline

The initial source baseline was imported from the existing `flamoris_ai` working tree.

It includes:

- `agents/umeko` personality, FLAMORIS knowledge, and character context;
- `src/flamoris_ai_agent` active console chat/runtime package;
- PostgreSQL schema, seed, and smoke-test SQL under `db`;
- the 2026-08-16 design notes and earlier prototype history.

The baseline is preserved intentionally so future phases can migrate from known working ideas instead of redesigning from memory. Existing assumptions such as direct Ollama access, machine-specific runtime identities, and the old DB shape are historical inputs, not automatically current architecture requirements.

See [the migration phases](docs/PHASES.md) and [Phase 0 runbook](docs/PHASE_0_RUNBOOK.md)
to register the currently served GPT-OSS model and run the Umeko console.

Secrets are not part of the baseline. The real `.env` remains untracked; only `.env.example` is committed.

## Development and layout

Install with `python -m pip install -e '.[dev]'`, then run `ruff check .`,
`ruff format --check .`, `pytest`, and `python -m build`.
Tests use fake providers and DB connections; no GPU or private credentials are needed.

| Path | Responsibility |
|---|---|
| `src/flamoris_ai_agent/` | Active runtime and packaged entry points |
| `agents/umeko/` | Active local personality/context, included in the wheel |
| `db/` | Existing PostgreSQL schema and seed, unchanged by packaging |
| `tests/` | Offline tests and installed-wheel smoke check |
| `docs/` | Current migration/runbook and forward design |
| `history/` | Imported records, prototypes, patches, and retired Ollama definitions |

Use `flamoris-agent-chat`, `flamoris-agent-register-runtime`, and
`flamoris-agent-verify-db` after installation. The former `apps/umeko_chat/*.py`
script paths have moved to the package. `python -m flamoris_ai_agent.chat`
is also supported. See [the history inventory](history/README.md) for moved records.

Source/editable installs keep using the repository-root `.env` and `agents/`.
Wheel installs use bundled context and process environment by default. For an
editable deployment context, set **an absolute** `FLAMORIS_AGENT_HOME` before
launch, containing `.env` and `agents/<agent-key>/{personality,flamoris,characters}.md`.
An explicit home is authoritative; missing identity files fail rather than silently
substituting the bundled Umeko. Unrelated working-directory `.env` files are never loaded.

## Intended scope

The Agent is planned to own:

- conversations and agent sessions;
- persistent memory and memory lifecycle;
- knowledge references and retrieval context;
- prompts and agent policies;
- tool registration, capability checks, and tool invocation;
- persistent Agent-level orchestration across intelligence and generation services;
- provenance needed to understand why an agent acted or answered as it did.

The repository now also contains the pre-repository Umeko/Ollama/PostgreSQL implementation as a baseline. That imported code documents what existed before the current repository architecture was defined; it must not be mistaken for the final target design.

## Ecosystem boundaries

```text
FLAMORIS application / Studio
           │
           ▼
    flamoris-ai-agent
      │            │
      │            └────────────► flamoris-generation-mcp
      │                            image / video / music / voice
      ▼
flamoris-intelligence-mcp
 language / reasoning / coding intelligence
```

These are boundaries, not mandatory layers.

### FLAMORIS Intelligence MCP

[flamoris-intelligence-mcp](https://github.com/flamoris-jp/flamoris-intelligence-mcp) is the planned MCP-native, provider-neutral gateway for language, reasoning, coding, and related intelligence capabilities.

The Agent may use it, but should not absorb model/provider runtime ownership. If Intelligence MCP performs bounded task coordination or multi-agent execution inside an intelligence request, the Agent still remains the authority for persistent Agent identity, conversation, memory, and long-lived workflow context.

### FLAMORIS Generation MCP

[flamoris-generation-mcp](https://github.com/flamoris-jp/flamoris-generation-mcp) owns generative-media and closely related media-analysis workflows, jobs, and assets.

The Agent may request generation, but should not become a second owner of generation job state.

### Product repositories

FLAMORIS 2D, Cutwork, Kachinco, Studio, and other applications remain authoritative for their own project/document state and editing behavior.

The Agent may assist those applications only through explicit product commands, queries, and permissions. It must not silently maintain a competing copy of product state.

### FLAMORIS Commons

Shared infrastructure that is not specifically Agent-domain logic belongs in [FLAMORIS Commons](https://github.com/flamoris-jp/flamoris-commons) or one of its dedicated shared repositories.

## Design principles

1. **Agent state has one authority**
   - Conversation state, memory, prompts, and agent policy should have explicit ownership.
   - Do not duplicate them across model providers or tools without a defined synchronization contract.

2. **Memory must be deliberate**
   - Persistent memory is user-impacting state, not an incidental cache.
   - Storage, provenance, retention, deletion, visibility, and update rules should be explicit before implementation.

3. **Tools are capabilities, not ambient authority**
   - Tool access should be scoped and inspectable.
   - Filesystem, network, product-editing, and credential-bearing actions require explicit boundaries.

4. **Treat retrieved content as untrusted**
   - Knowledge sources, webpages, files, messages, and model outputs may contain malicious or misleading instructions.
   - Retrieved content must not silently redefine system policy or tool permissions.

5. **Provider-neutral intelligence access**
   - Local and remote models should be replaceable behind explicit interfaces.
   - Provider names should not become the Agent's public architecture.

6. **Human-authoritative**
   - AI can plan, reason, draft, inspect, and operate tools within granted capabilities.
   - Product state, security policy, licensing, and release decisions remain human-authoritative.

## Repository policy

This repository follows the shared [FLAMORIS Repository Policy](https://github.com/flamoris-jp/flamoris-commons/blob/main/docs/repository-policy.md).

Agent-specific privacy, memory, and tool-safety rules supplement that shared policy.

## License

Code and documentation in this repository are licensed under the [Apache License 2.0](LICENSE), unless otherwise noted.

AI models, model weights, datasets, retrieved knowledge sources, generated media, third-party prompts, and provider-hosted assets are not automatically covered by this repository's license. Their applicable licenses and usage terms must be checked separately.

Commercial use of Apache-2.0 licensed FLAMORIS code does not require permission.

FLAMORIS software is provided as-is and does not include guaranteed individual support. AI-assisted self-support is encouraged.

---

## 日本語

FLAMORIS AI Agentは、FLAMORISで長く動き続けるAI Agentのためのリポジトリです。

**旧梅子の実装を保存済みです。Phase 0ではllama.cpp経由のGPT-OSS接続を追加し、実際のdeployment環境での確認を別途行います。**

将来的に、以下のAgent側の状態と振る舞いを担当します。

- Conversation / Session
- Memoryとそのlifecycle
- Knowledge参照・検索context
- Prompt / Agent policy
- Tool登録、capability確認、tool実行
- Intelligence MCP / Generation MCPへのorchestration
- Agentの判断や操作を追跡するためのprovenance

### 境界

- **会話・Memory・Prompt・Agent policy** はAI Agentがauthorityを持つ。
- **LLM / reasoning / coding intelligence** は `flamoris-intelligence-mcp` 側の責務。
- **画像・動画・音楽・音声の生成job / workflow / asset** は `flamoris-generation-mcp` 側の責務。
- **2D / Cutwork / Kachinco / Studioなどの制作データ** は各アプリ自身がauthorityを持つ。
- AI Agentは便利だからといって、全部の状態を抱え込まない。記憶力が良すぎる物置にはしない。🐈

### Memoryについて

Memoryは単なるcacheではなく、ユーザーに影響する永続状態として扱います。

実装時には、少なくとも保存対象、出所、保持期間、更新、削除、可視性を明示します。

### Toolについて

ToolはAgentに無制限の権限を与える仕組みではありません。

filesystem、network、制作アプリ編集、credentialを伴う操作には、明確なscopeとpermission boundaryを持たせます。

### ライセンス

このリポジトリのコードとドキュメントは、明記がない限りApache License 2.0です。

AI model、model weights、dataset、Knowledge source、生成物、第三者由来のprompt、provider側assetなどには別のライセンスや利用条件が適用される場合があります。それぞれ確認してください。

