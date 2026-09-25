# FLAMORIS AI v0.1 構築・設計記録

作成日: 2026-08-16  
DB名: `flamoris_ai`  
通称: **flamoris_ai（売ってません！）**

---

# 0. 目的

梅子専用DBではなく、FLAMORISで将来動く複数Agentの共通基盤を作る。

v0.1で受け止めるもの:

```text
複数Agent
多段Project
Agent間共有知識
Agent固有記憶
会話ログ
Relay
Host / Application / Instance追跡
Job / Tool実行履歴
将来のpgvector
```

ただし今回実際に動かすのは、

```text
愛乃
↓
Local Host / Umeko Chat instance
↓
梅子
↓
Ollama
↓
flamoris_ai / PostgreSQL
```

まで。

---

# 1. DB全体

```text
flamoris_ai
│
├─ core
│  ├─ schema_migrations
│  ├─ projects
│  ├─ humans
│  ├─ agents
│  └─ agent_projects
│
├─ runtime
│  ├─ hosts
│  ├─ applications
│  ├─ models
│  └─ instances
│
├─ chat
│  ├─ conversations
│  ├─ participants
│  ├─ conversation_sessions
│  └─ messages
│
├─ memory
│  ├─ knowledge_items
│  ├─ knowledge_grants
│  ├─ memories
│  ├─ memory_shares
│  └─ embedding_models
│
├─ relay
│  ├─ events
│  └─ deliveries
│
└─ ops
   ├─ jobs
   ├─ runs
   └─ tool_calls
```

Agent単位でSchemaを分けず、機能単位でSchemaを分ける。

Agentは `agent_id` で区別する。

---

# 2. Project階層

`core.projects.parent_project_id` が自分自身のテーブルを参照する。

任意段数にできる。

初期Seed:

```text
FLAMORIS
└─ AI
   └─ 梅子
```

各Projectには2種類の識別子がある。

```text
slug
project_key
```

`slug` は階層表示向け。

`project_key` はアプリから参照する安定キー。

初期値:

```text
flamoris
flamoris.ai
flamoris.ai.umeko
```

Projectを将来別階層へ移動しても、アプリ側は `project_key` を使う。

---

# 3. Project path確認

Schema作成後:

```sql
SELECT
    project_key,
    name,
    depth,
    slug_path_text,
    name_path_text
FROM core.project_paths
ORDER BY slug_path_text;
```

期待:

```text
flamoris           FLAMORIS   0   flamoris
flamoris.ai        AI         1   flamoris/ai
flamoris.ai.umeko  梅子       2   flamoris/ai/umeko
```

---

# 4. Host / Application / Instance

これは分離する。

```text
Host
= どのマシン / VMか

Application
= 何のソフトか

Instance
= 今回起動した具体的な1プロセス
```

今回:

```text
Host        Local Host
Application Umeko Chat
Instance    chat.pyを起動するたびに新規UUID
```

同じLocal Host上で梅子を10回起動したら、
`runtime.instances` は10件残る。

各messageには `origin_instance_id` が入る。

これで後から、

```text
この発言は
Local Hostの
Umeko Chatの
どの起動個体が処理したか
```

まで追跡できる。

---

# 5. AgentとModelは別

```text
core.agents
梅子

runtime.models
ollama:umeko
```

を別管理する。

将来:

```text
Qwen2.5 7B
↓
別7B
↓
12B
↓
FLAMORIS専用モデル
```

と脳を交換しても、梅子の `agent_id` は変えない。

---

# 6. PostgreSQL hostへ入る

## Dockerの場合

まずコンテナ確認:

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
```

PostgreSQLコンテナへ:

```bash
docker exec -it <コンテナ名> psql -U postgres
```

## Ubuntu直接インストールの場合

```bash
sudo -u postgres psql
```

---

# 7. PostgreSQLバージョン確認

psql:

```sql
SELECT version();
SELECT gen_random_uuid();
```

どちらも正常なら続行。

終了:

```text
\q
```

---

# 8. DB Rolesを作る

役割を2つに分ける。

```text
flamoris_ai_owner
= DB / Schema / Table所有
= NOLOGIN

flamoris_ai_app
= 梅子や将来のAgentが使うRuntime login
```

psqlをpostgres管理者として開く。

```sql
CREATE ROLE flamoris_ai_owner NOLOGIN;
CREATE ROLE flamoris_ai_app LOGIN;
```

Runtime roleのパスワードは対話で設定する。

```text
\password flamoris_ai_app
```

パスワード文字列をSQLやShell historyへ直書きしない。

既にRoleがある場合はCREATEを繰り返さない。

確認:

```text
\du
```

---

# 9. flamoris_ai DBを作る

postgres管理者のpsql:

```sql
CREATE DATABASE flamoris_ai
    OWNER flamoris_ai_owner
    ENCODING 'UTF8';
```

接続権限:

```sql
GRANT CONNECT ON DATABASE flamoris_ai TO flamoris_ai_app;
```

確認:

```text
\l
```

---

# 10. Schemaを作る

配布ZIPの:

```text
db/01_schema.sql
```

を実行する。

方法A: DBeaverから `flamoris_ai` DBへ管理者接続してSQLスクリプトを実行。

方法B: SQLファイルをPostgreSQL hostへ置き、psqlから:

```bash
psql -U postgres -d flamoris_ai -f 01_schema.sql
```

Dockerなら:

```bash
docker exec -i <コンテナ名> \
  psql -U postgres -d flamoris_ai < 01_schema.sql
```

`01_schema.sql` 自身が、

```sql
SET ROLE flamoris_ai_owner;
```

して各SchemaとTableをowner権限で作る。

---

# 11. 初期データを入れる

次に:

```text
db/02_seed_umeko.sql
```

を実行する。

DBeaverでもpsqlでもよい。

これで登録:

```text
Human
  akino / 愛乃

Agent
  umeko / 梅子

Projects
  FLAMORIS
  └─ AI
     └─ 梅子

Host
  local-host

Application
  umeko-chat

Model
  ollama:umeko
  base = qwen2.5:7b
```

---

# 12. DB smoke test

`db/03_smoke_test.sql` を実行。

以下が見えればOK。

```text
schema version 0.1
FLAMORIS / AI / 梅子
umeko / 梅子
local-host
umeko-chat
ollama:umeko
```

---

# 13. Local Hostへ配置

最終配置:

```text
C:\FLAMORIS\ai\umeko\
├─ Modelfile
├─ personality.md
├─ flamoris.md
├─ characters.md
├─ .env
├─ requirements.txt
└─ app\
   ├─ chat.py
   ├─ db.py
   └─ verify_db.py
```

ZIP内の以下をコピー:

```text
app/chat.py
app/db.py
app/verify_db.py
requirements.txt
.env.example
.gitignore
```

---

# 14. Python package

仮想環境:

```powershell
cd C:\FLAMORIS\ai\umeko\app
.\.venv\Scripts\Activate.ps1
```

プロジェクトルートのrequirementsを使う:

```powershell
pip install -r ..\requirements.txt
```

導入:

```text
requests
psycopg[binary]
python-dotenv
```

---

# 15. .env

ルートへコピー:

```powershell
Copy-Item ..\.env.example ..\.env
notepad ..\.env
```

重要箇所:

```text
PGDATABASE=flamoris_ai
PGUSER=flamoris_ai_app
PGPASSWORD=実際のパスワード

FLAMORIS_HUMAN_KEY=akino
FLAMORIS_AGENT_KEY=umeko
FLAMORIS_PROJECT_KEY=flamoris.ai.umeko
FLAMORIS_HOST_KEY=local-host
FLAMORIS_APPLICATION_KEY=umeko-chat
FLAMORIS_MODEL_KEY=ollama:umeko
```

---

# 16. DB接続確認

```powershell
cd C:\FLAMORIS\ai\umeko\app
.\.venv\Scripts\Activate.ps1
python verify_db.py
```

期待例:

```text
FLAMORIS AI DB接続 OK
schema version : 0.1
project        : flamoris.ai.umeko / FLAMORIS / AI / 梅子
agent          : umeko / 梅子
host           : local-host / Local Host
application    : umeko-chat / Umeko Chat
model          : ollama:umeko / ollama:umeko (qwen2.5:7b)
```

---

# 17. 梅子起動

```powershell
python chat.py
```

起動時:

```text
梅子を起動しました。終了は /bye
conversation_id = ...
instance_id     = ...
愛乃>
```

この `instance_id` は起動するたびに変わる。

---

# 18. 保存されるもの

起動時:

```text
runtime.instances
```

へ1件。

会話開始:

```text
chat.conversations
chat.participants
chat.conversation_sessions
```

へ登録。

愛乃と梅子の発言:

```text
chat.messages
```

へ全保存。

終了:

```text
runtime.instances.ended_at
chat.conversations.ended_at
chat.conversation_sessions.left_at
```

を記録。

---

# 19. 会話確認SQL

最近のConversation:

```sql
SELECT
    c.id,
    c.created_at,
    c.ended_at,
    a.display_name AS agent,
    p.name_path_text AS project
FROM chat.conversations AS c
LEFT JOIN core.agents AS a
  ON a.id = c.primary_agent_id
LEFT JOIN core.project_paths AS p
  ON p.id = c.project_id
ORDER BY c.created_at DESC;
```

最近のMessage:

```sql
SELECT
    m.ordinal,
    m.role,
    cp.display_name AS sender,
    m.content,
    h.display_name AS host,
    app.name AS application,
    i.id AS instance_id,
    m.created_at
FROM chat.messages AS m
LEFT JOIN chat.participants AS cp
  ON cp.id = m.sender_participant_id
LEFT JOIN runtime.instances AS i
  ON i.id = m.origin_instance_id
LEFT JOIN runtime.hosts AS h
  ON h.id = i.host_id
LEFT JOIN runtime.applications AS app
  ON app.id = i.application_id
ORDER BY m.ordinal DESC
LIMIT 100;
```

ここで「どのLocal Host / どのAP instanceか」まで見える。

---

# 20. Knowledge共有設計

`memory.knowledge_items`

にKnowledge本体。

`memory.knowledge_grants`

で:

```text
global
project
agent
```

を設定。

例:

```text
FLAMORISとは何か
→ global

Akino 3DのHair設計
→ project

梅子だけに与える補助知識
→ agent
```

---

# 21. Memory

Agent自身の経験:

```text
memory.memories
```

に保存する。

例:

```text
owner_agent = 梅子
project = FLAMORIS / AI / 梅子
memory = 愛乃と○○について話した
```

デフォルトはprivate。

共有したいMemoryだけ:

```text
memory.memory_shares
```

へ登録する。

---

# 22. Relay

Agent間通信は:

```text
relay.events
relay.deliveries
```

へ統合できる設計。

例:

```text
梅子
↓
event
↓
美祥
```

イベントには:

```text
project_id
sender_agent_id
source_instance_id
correlation_id
causation_event_id
payload
```

を持つ。

つまり「誰が・どこで動いていて・何をきっかけに送ったか」を追える。

---

# 23. Ops

Agentが実作業を始めたら:

```text
ops.jobs
ops.runs
ops.tool_calls
```

を使う。

例:

```text
George
→ バックアップJob

梅子
→ Blender補助Job

美祥
→ 画像生成Tool call
```

実行元instanceも記録する。

---

# 24. pgvector

まだ入れない。

現在:

```text
保存 ✅
正規化 ✅
共有範囲 ✅
Agent固有化 ✅
意味検索 ❌
```

次のMemory段階でpgvectorを追加する。

Knowledge / Memory原文とEmbeddingを別管理する予定。

Embeddingモデルを交換しても原文を壊さない。

---

# 25. 今回の設計で重要なID

```text
agent_id
= 誰か

project_id
= 何の仕事か

host_id
= どのマシンか

application_id
= 何のアプリか

instance_id
= そのアプリのどの起動個体か

conversation_id
= どの会話か

correlation_id
= どの一連のイベントか
```

この軸でFLAMORIS AI全体をつなぐ。

---

# 26. 現在地

```text
梅子ローカルLLM             ✅
外部人格md                   ✅
複数Agent DB設計             ✅
多段Project                  ✅
Host/Application/Instance    ✅
Knowledge共有構造            ✅
Memory構造                   ✅
Relay構造                    ✅
Ops構造                      ✅
flamoris_ai DB               ← 今回作成
梅子会話保存                 ← 今回接続
過去会話の検索               次
pgvector                     次以降
長期記憶                     次以降
```

---

# 27. 次回開始地点

DBと `chat.py` が動いたら次は、

```text
保存した会話
↓
Memory候補抽出
↓
Agent固有Memory
↓
Project/Global Knowledge
↓
pgvector
↓
意味検索
```

へ進む。

梅子専用の小屋ではなく、
FLAMORIS AI全員が住める基盤として育てる。
