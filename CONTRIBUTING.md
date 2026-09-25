# Contributing to FLAMORIS AI Agent

Thank you for your interest in FLAMORIS.

This repository is intended to become the persistent Agent runtime for FLAMORIS. Keep changes focused on Agent-owned behavior and state.

## Before contributing

Issues are welcome from everyone. Pull requests are accepted only from repository collaborators. Please open an Issue to propose documentation fixes or implementation changes.

Please open an Issue first for substantial changes involving:

- memory or persistence;
- tool/capability permissions;
- conversation or session semantics;
- knowledge retrieval;
- provider integration;
- cross-repository boundaries;
- externally visible APIs or protocols.

Before adding a feature, confirm that it belongs in the Agent rather than `flamoris-intelligence-mcp`, `flamoris-generation-mcp`, a product repository, or FLAMORIS Commons.

## Pull requests

Please:

- keep changes focused;
- identify state authority;
- document privacy and permission impact;
- include tests where practical;
- preserve public behavior unless intentionally changed;
- avoid unnecessary dependencies;
- distinguish implemented behavior from future plans.

AI-assisted contributions are welcome. Contributors remain responsible for reviewing, testing, licensing, and understanding submitted changes.

## Licensing

Unless explicitly stated otherwise, code and documentation contributions are submitted under Apache License 2.0.

Do not add third-party models, weights, datasets, knowledge corpora, prompts, media, generated assets, or provider-hosted material without documenting applicable licenses and redistribution terms.

## Support

FLAMORIS does not provide guaranteed individual support.

Use repository documentation, Issues, tests, logs, and source code as primary references. AI-assisted self-support is encouraged.

---

# FLAMORIS AI Agent へのコントリビューション

FLAMORISに興味を持っていただきありがとうございます。

Issueはどなたでも歓迎します。Pull Requestはリポジトリのcollaboratorのみ受け付けています。修正、機能、ドキュメント変更などの提案はIssueからお願いします。

このリポジトリは、FLAMORISの永続的なAI Agent runtimeを担当する予定です。変更はAgent自身が持つ状態と振る舞いに絞ってください。

Memory、永続化、Tool permission、Conversation/Session、Knowledge retrieval、provider連携、複数リポジトリへ影響する境界変更は、実装前にIssueで整理してください。

機能を追加する前に、`flamoris-intelligence-mcp`、`flamoris-generation-mcp`、各制作アプリ、FLAMORIS Commonsのどこへ置くべきか確認してください。

コードとドキュメントは、明記がない限りApache License 2.0です。第三者のAI model、weights、dataset、Knowledge corpus、prompt、media、生成assetなどには別の条件が適用される場合があるため、必ず確認・明記してください。
