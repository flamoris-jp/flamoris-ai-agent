# Security Policy

## Reporting a vulnerability

Do not post suspected vulnerabilities, credentials, tokens, private conversation content, memory data, personal data, private generated media, or other sensitive information in a public Issue.

Use GitHub private vulnerability reporting when available. Otherwise contact the FLAMORIS maintainers through an appropriate private channel before sharing sensitive details.

Non-sensitive security hardening and design discussion may use normal GitHub Issues.

## Agent-specific security scope

The Agent crosses trust boundaries between users, model providers, retrieved knowledge, tools, applications, filesystems, and network services.

Treat the following as security-sensitive:

- persistent memory and conversation storage;
- data sent to remote providers;
- tool permissions and capability grants;
- prompt injection and untrusted retrieved content;
- filesystem and network access;
- credential-bearing tools;
- destructive or non-idempotent actions;
- product editing and revision conflicts;
- model-generated commands, URLs, paths, and tool arguments;
- logging of private prompts, memory, or tool results;
- retention and deletion of user data.

Model output is untrusted input. It must not bypass tool validation or permission checks.

Do not commit live credentials, private datasets, private memory stores, conversation exports, or private generated outputs.

## Supported versions

FLAMORIS is developed as an open-source project without a guaranteed support window or security-response SLA.

Security fixes are generally applied to the current maintained codebase.

## Scope

This policy applies to code and documentation maintained by FLAMORIS.

Third-party model providers, models, weights, datasets, knowledge sources, services, and tools may have separate security, privacy, licensing, and support terms.

---

# セキュリティポリシー

公開Issueへ、脆弱性情報、credential、token、非公開Conversation、Memoryデータ、個人情報、非公開生成物などを投稿しないでください。

AI Agentは、ユーザー、model provider、Knowledge、Tool、制作アプリ、filesystem、network serviceの間をまたぐため、特に以下をsecurity-sensitiveとして扱います。

- 永続Memory / Conversation
- remote providerへ送信するデータ
- Tool permission / capability
- prompt injection / untrusted content
- filesystem / network access
- credentialを扱うTool
- destructive / non-idempotent operation
- 制作アプリ編集とrevision conflict
- AIが生成したcommand / URL / path / tool argument
- private prompt / Memory / tool resultのlogging
- user dataのretention / deletion

Model outputは信頼済み入力として扱わず、Tool validationやpermission checkを迂回させないでください。
