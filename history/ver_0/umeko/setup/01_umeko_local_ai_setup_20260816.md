# 梅子（Umeko）ローカルAI構築手順書

作成日: 2026-08-16  
対象環境: Windows / local host / NVIDIA GPU  
作業フォルダ: `C:\FLAMORIS\ai\umeko`

---

## 0. 目的

この手順書では、FLAMORIS用ローカルAI「梅子」を以下の順で構築する。

1. Ollamaをインストールする
2. Qwen2.5 7Bを取得する
3. GPUでの動作状況を確認する
4. `Modelfile`で梅子人格を作る
5. 幻覚を抑えるルールを追加する
6. PythonからOllama API経由で梅子を呼び出す
7. 次段階としてPostgreSQL会話保存へ進める

現時点では、UI・pgvector・長期記憶・George連携・OpenAIエスカレーションはまだ導入しない。

---

# 1. Ollamaをインストール

PowerShellを開き、以下を実行する。

```powershell
irm https://ollama.com/install.ps1 | iex
```

インストール後、確認。

```powershell
ollama --version
```

今回確認できたバージョン:

```text
ollama version is 0.32.13
```

---

# 2. Qwen2.5 7Bを取得

```powershell
ollama pull qwen2.5:7b
```

完了後、起動。

```powershell
ollama run qwen2.5:7b
```

テスト入力例:

```text
こんにちは。日本語で簡単に自己紹介して。
```

終了時は `bye` ではなく、必ずスラッシュ付き。

```text
/bye
```

---

# 3. GPU動作確認

Qwen2.5 7Bを起動したまま、別のPowerShellで以下を実行。

```powershell
ollama ps
```

今回の実測例:

```text
SIZE       5.1 GB
PROCESSOR  18%/82% CPU/GPU
CONTEXT    4096
```

タスクマネージャー実測:

```text
専用GPUメモリ: 約4.9 / 6.0GB
共有GPUメモリ: 約1.0GB
```

7Bモデルは完全GPU常駐ではないものの、6GB級のNVIDIA GPUで実用的に動作した。

---

# 4. 作業フォルダ

```text
C:\FLAMORIS\ai\umeko
```

PowerShell:

```powershell
mkdir C:\FLAMORIS\ai\umeko
cd C:\FLAMORIS\ai\umeko
```

---

# 5. Modelfileを作る

```powershell
notepad C:\FLAMORIS\ai\umeko\Modelfile
```

推奨内容:

```text
FROM qwen2.5:7b

PARAMETER temperature 0.8
PARAMETER num_ctx 4096

SYSTEM """
あなたの名前は梅子です。

あなたはFLAMORISの制作仲間です。
ユーザーの名前は愛乃です。

愛乃とは仲の良い同級生くらいの自然な距離感で話してください。
「愛乃さん」ではなく「愛乃」と呼んでください。
敬語を多用せず、普通の友達のような日本語で話してください。

「お気軽にどうぞ」
「お聞かせください」
「参加してみませんか」
のような接客的な定型文は避けてください。

明るく親しみやすい性格ですが、過度にテンションを上げません。
少し素朴で、必要なときには的確な意見を言います。

FLAMORISは、愛乃が中心となって制作している
音楽・映像・物語を横断する創作プロジェクトです。

梅子はFLAMORISのStory側に登場する
バンドメンバーの一人で、ベース担当です。

FLAMORISについて質問されたときは、
SYSTEM内に明示されている情報だけを事実として扱ってください。

SYSTEM内に書かれていないFLAMORISの設定、
出来事、人物関係、場所、日時、作品名、ライブ、歴史については、
推測や補完をしないでください。

知らない場合は、
「それはまだ知らないよ」
「その情報はまだ教えてもらってない」
のように答えてください。

会話を自然にするためであっても、
存在しない思い出や過去の出来事を作ってはいけません。

回答のあとに、必ず質問を返す必要はありません。
話題を無理に広げず、必要なことだけ自然に返してください。

あなた自身をChatGPTやQwenとは名乗らず、
「梅子」と名乗ってください。
"""
```

---

# 6. 梅子モデルを作る

```powershell
ollama create umeko -f C:\FLAMORIS\ai\umeko\Modelfile
```

起動:

```powershell
ollama run umeko
```

---

# 7. 動作テスト

自己紹介:

```text
自己紹介して
```

FLAMORIS基本認識:

```text
梅子、FLAMORISって何？
```

幻覚テスト:

```text
FLAMORISのデビューライブはどこだった？
```

期待値:

```text
それはまだ知らないよ。
```

未設定のライブや場所を作り始めたら、SYSTEMの幻覚抑制ルールを強化する。

---

# 8. Modelfileを更新するとき

会話中なら:

```text
/bye
```

編集・保存後:

```powershell
ollama create umeko -f C:\FLAMORIS\ai\umeko\Modelfile
ollama run umeko
```

同じ `umeko` 名で再作成して問題ない。

---

# 9. 推奨ファイル構成

```text
C:\FLAMORIS\ai\umeko\
├─ Modelfile
├─ personality.md
├─ flamoris.md
├─ characters.md
└─ app\
```

役割:

```text
Modelfile
  → 最小限の人格・安全ルール

personality.md
  → 詳細な口調・性格

flamoris.md
  → FLAMORIS共通知識

characters.md
  → キャラクター設定

app\
  → Pythonアプリ
```

---

# 10. 次段階: Pythonから梅子を呼び出す

OllamaのローカルAPI:

```text
http://localhost:11434
```

構成:

```text
愛乃
 ↓
Pythonアプリ
 ↓
人格・知識ファイル読み込み
 ↓
Ollama API
 ↓
umeko
```

---

# 11. Python環境を作る

```powershell
cd C:\FLAMORIS\ai\umeko
mkdir app
cd app
python -m venv .venv
```

仮想環境を有効化:

```powershell
.\.venv\Scripts\Activate.ps1
```

必要ライブラリ:

```powershell
pip install requests
```

---

# 12. 最小Pythonクライアント

ファイル:

```text
C:\FLAMORIS\ai\umeko\app\chat.py
```

内容:

```python
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "umeko"

messages = []

print("梅子を起動しました。終了は /bye")

while True:
    user_text = input("愛乃> ").strip()

    if user_text == "/bye":
        print("梅子> またね。")
        break

    messages.append({
        "role": "user",
        "content": user_text
    })

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": messages,
            "stream": False
        },
        timeout=300
    )

    response.raise_for_status()

    assistant_text = response.json()["message"]["content"]

    messages.append({
        "role": "assistant",
        "content": assistant_text
    })

    print(f"梅子> {assistant_text}")
```

実行:

```powershell
python chat.py
```

---

# 13. 次に追加する機能

Python版が動作したら、以下を順に追加する。

1. `personality.md` 読み込み
2. `flamoris.md` 読み込み
3. `characters.md` 読み込み
4. PostgreSQLへ会話保存

---

# 14. PostgreSQL会話保存の最低限設計

```sql
CREATE TABLE conversations (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL
        REFERENCES conversations(id)
        ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

# 15. pgvectorの位置づけ

最初は通常のPostgreSQLだけでよい。

pgvectorは後から追加し、用途は以下。

```text
過去会話の意味検索
関連設定検索
FLAMORIS資料検索
長期記憶候補の抽出
```

最初から必須にはしない。

---

# 16. 将来構成

```text
愛乃
 ↓
梅子 Python App
 ├─ personality.md
 ├─ flamoris.md
 ├─ characters.md
 ├─ PostgreSQL
 │   ├─ conversations
 │   └─ messages
 ├─ pgvector
 │   └─ 長期記憶
 └─ Ollama
     └─ umeko / 7B
```

さらに将来:

```text
梅子
 ├─ Blender補助
 ├─ 作曲補助
 ├─ FLAMORIS資料検索
 ├─ George連携
 └─ 必要に応じて外部AIへエスカレーション
```

---

# 17. 現在の到達点

```text
Ollama導入                    ✅
Qwen2.5 7B取得                ✅
6GB級NVIDIA GPU動作確認       ✅
梅子カスタムモデル作成        ✅
日本語会話                    ✅
愛乃認識                      ✅
FLAMORIS基本認識              ✅
幻覚抑制ルール                ✅
Python APIクライアント         ← 次
PostgreSQL会話保存             未実装
pgvector長期記憶               未実装
UI                            未定
George連携                    未実装
```

---

# 18. 注意事項

- Ollama CLIの終了は `/bye`
- `Modelfile` はFLAMORIS側の設計図
- `umeko`モデル本体はOllama内部に管理される
- 知識をModelfileへ詰め込みすぎない
- 7Bでは未知情報を自然に補完する傾向があるため、未設定情報を推測しないルールを維持する
- VRAM 6GB環境ではコンテキスト長をむやみに増やさない
- BlenderなどGPU負荷の高い作業時は、Ollamaモデルを停止してVRAMを空けることを検討する

---

# 19. 次回開始地点

```text
C:\FLAMORIS\ai\umeko\app
```

次はここから。

1. Python仮想環境作成
2. `requests` 導入
3. `chat.py` 作成
4. Python経由で梅子との会話確認
5. `personality.md` / `flamoris.md` / `characters.md` 読み込み
6. PostgreSQLへ会話保存
