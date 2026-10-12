# AI Agent：Updaterの入力値と導入後の設定

対象は公開済み1.0.2のインストール定義です。別の版では選定Releaseのカタログと[インストール定義](../release/install-recipe.json)を照合します。
Updaterの画面には短い項目名が表示されます。本書で用途・取得元・空欄時の動作を確認してください。
既定値は入力欄の初期値で、generate=true以外の欄を空にしても自動生成されません。
共通のDB・秘密値の扱い、配置の調べ方、作業の順番は[共通設定ガイド](https://github.com/flamoris-jp/flamoris-updater/blob/main/docs/APPLICATION_SETUP.md)にあります。

## 導入前に用意するもの

PostgreSQLの管理者接続、Agentから到達できるllama.cpp、利用するHuman／Agent／Projectの名前を用意します。
Updaterが新規DB・role・schemaとmigrationを作成します。導入後に初期schemaをもう一度流す手順ではありません。

## Updaterに入力する値

| 項目（キー） | 用途・値の用意 | 初期表示／空欄の動作 |
| --- | --- | --- |
| 待受ポート（PORT） | Agentサービスの入口。ホスト上で未使用のポートを選ぶ | 8768 |
| PostgreSQL管理者接続（ADMIN_DSN） | 新規DB・role作成に使う既存管理者の接続文字列。DB管理者から取得。Studioのログインや外部API keyではない | 必須、自動生成なし |
| DBホスト（PGHOST） | Agent実行環境から到達できるPostgreSQLの名前／アドレス。既存DBの配置から確認 | 必須、自動生成なし |
| DBポート（PGPORT） | 既存PostgreSQLの待受ポートを確認 | 5432 |
| 新規DB名（DATABASE） | このAgent用に新しく作るDBの名前を選ぶ | flamoris_ai。既存DBの再初期化には使わない |
| DB所有者パスワード（OWNER_PASSWORD） | 新しく作るflamoris_ai_owner用。既存DB管理者のパスワードとは別 | 空欄でUpdaterが生成 |
| アプリ用DBパスワード（RUNTIME_PASSWORD） | 新しく作るflamoris_ai_app用。AgentがDBへ接続する値 | 空欄でUpdaterが生成 |
| Agent接続トークン（AGENT_TOKEN） | Studio等のbackendがAgent HTTPへ接続する共有秘密値。Agent側で作り、StudioのAGENT_TOKENへ同じ値を入れる | 空欄でUpdaterが生成。外部サイトから取得しない |
| llama.cppのURL（INTELLIGENCE_URL） | 既存モデルサービスのbase URLを、そのservice設定から取得。Intelligence MCP／HubのURLではない | http://127.0.0.1:8081。到達性は実行環境から確認 |
| Studio委譲者キー（DELEGATOR_KEY） | Studioからの利用を識別する運用者が決める名前。秘密tokenではない。Agent・Studioの委譲者設定とDB権限で一致させる | 空欄は単一principal。Studio共有利用には別途設定・権限が必要 |

AGENT_TOKENはruntime.envのAGENT_MCP_TOKENへ保存されます。名前にMCPが含まれますが、内部HTTPの認証にも使う現行の設定名です。
生成した値の所在・相手への設定方法は[秘密値の対応表](https://github.com/flamoris-jp/flamoris-updater/blob/main/docs/APPLICATION_SETUP.md#トークンとパスワードは何者か)を参照してください。

## 導入後にユーザー／AIが行うこと

1. Updaterでアプリを起動し、初回設定を進める。DB接続と実際に提供されるモデルIDを確認する。
2. Human／Agent／Project／モデル等のidentityを登録する。[Agent導入手順](INSTALL.md)のidentity・検証部分を参照し、Updaterが済ませたpackage導入・schema作成は繰り返さない。
3. 人格を設定する。ファイルcontextは[Agent context](AGENT_CONTEXT.md)、DBの人格revisionと編集権限は[設定契約](ASSISTANT_SETTINGS_V1.md)を使う。名前だけの登録と人格本文の設定は別。
4. Studioと連携する場合、[内部HTTP](INTERNAL_EXECUTION.md)に従って委譲者・membership／delegation・モデル利用・人格read/edit権限を登録する。必要なAGENT_SETTINGS_ENABLEDやモデルregistryを設定する。service tokenだけでは利用者の権限は作られない。
5. Studio側にAgent origin、同じtoken、正確なStudio user UUID→Human／Agent／Project対応を設定する。
6. DB・モデル・principalの利用可否、対象ユーザーの会話を個別に確認する。外部providerは選んで設定した場合だけ確認する。

任意のOpenAI等のAPI keyはprovider側で発行する別の秘密値で、AGENT_TOKENとは別物です。価格・上限・モデルgrantと共に[内部推論設定](INTERNAL_EXECUTION.md)へ設定します。ローカルだけの導入にAPI keyは不要です。

## AIに渡すとき

選定版、Updaterの配置情報、secretを除く設定名と値、単独利用かStudio連携か、登録したidentityと未完了項目を伝えます。
秘密値は会話へ貼らず、既存の管理者設定を必要な項目だけローカルで扱います。
起動healthが成功しても、人格・モデル・権限・会話設定の完了とはしません。
