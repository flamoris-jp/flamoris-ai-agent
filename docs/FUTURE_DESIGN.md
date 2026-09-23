# FLAMORIS AI Future Design

このファイルは v0.1 の「まだ実装しないが、今の設計で受け止めるもの」を記録する。

## 1. Project inheritance

`core.projects.parent_project_id` で任意段数の階層を作る。

例:

```text
FLAMORIS
├─ Music
│  └─ Album
│     └─ Song
├─ MV
│  └─ Akino 3D
│     └─ Hair
└─ AI
   ├─ Umeko
   ├─ Misaki
   └─ George
```

将来のKnowledge検索では、現在Projectから親へ遡り、

```text
root知識
+ 親Project知識
+ 現在Project知識
+ Agent固有知識
```

を合成する。

`core.project_paths` は表示用。
祖先取得は `WITH RECURSIVE` で実装する。

## 2. Agent != Model

Agent identity:

```text
梅子
```

Model identity:

```text
Ollama / umeko / Qwen2.5 7B
```

は別物。

将来モデルを交換しても `core.agents.id` は維持する。

## 3. Host / Application / Instance

3階層を分離する。

```text
Host
└─ Application
   └─ Instance
```

例:

```text
Mango
└─ Umeko Chat
   ├─ instance A
   └─ instance B
```

再起動ごとに `runtime.instances` が1件増える。

`chat.messages.origin_instance_id` により、
各メッセージがどの実行個体から発生したか追跡できる。

`runtime.hosts.parent_host_id` を使えば、

```text
Mango
└─ Apricot VM
```

のようなHost階層も表現できる。

## 4. Multi-agent conversation

`chat.conversations` にAgentを1個だけ固定しない。

`chat.participants` で、

```text
愛乃
梅子
美祥
George
```

など複数参加者を1会話に登録できる。

## 5. Knowledge vs Memory vs Log

3種類を分離する。

### Knowledge

正式設定・資料・事実。

`memory.knowledge_items`

### Memory

Agentが経験から保持する記憶。

`memory.memories`

### Raw log

発言そのもの。

`chat.messages`

これにより「公式設定」と「昔そう話した」を混同しにくくする。

## 6. Shared and private knowledge

`memory.knowledge_grants` で、

```text
global
project
agent
```

の共有範囲を表現する。

Agent固有Memoryは `owner_agent_id` を持つ。

Agent間でMemoryを共有したい場合は `memory.memory_shares` を使う。

## 7. pgvector

v0.1では入れない。

将来migrationで `vector` extensionと `memory.embeddings` を追加する。

Embeddingには最低限、

```text
source type
source id
embedding model id
vector
created_at
```

を持たせる。

Embeddingモデル交換時に原文データを壊さないよう、
Knowledge/Memory本体とVectorを分離する。

## 8. Relay

`relay.events` をAgent間イベントの共通バスにする。

`correlation_id`
で一連の処理をまとめる。

`causation_event_id`
で直接の因果イベントを記録する。

例:

```text
愛乃の入力
↓
Relay event A
↓
梅子処理 B
↓
Memory C
↓
美祥へのevent D
```

A〜Dを同一correlationで追跡可能にする。

## 9. Ops

Agentが実作業を始めたら、

```text
ops.jobs
ops.runs
ops.tool_calls
```

に記録する。

Blender、生成処理、バックアップ、MCP、外部APIなどの監査ログとして利用する。

## 10. Context

Projectより短命な作業文脈が必要になった場合だけ、
将来 `core.contexts` を追加する。

v0.1では作らない。

不要な抽象化を先に増やさない。
