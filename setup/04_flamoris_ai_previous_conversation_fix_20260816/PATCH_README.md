# 前回conversation読込 UUID修正パッチ

対象:

```text
C:\FLAMORIS\flamoris_ai\apps\umeko_chat\chat.py
```

このファイルだけ上書きする。

## 修正内容

前回conversationにはPostgreSQLから取得した:

```text
UUID
datetime
```

が含まれる。

これをそのまま `system_context JSONB` へ保存するとPython標準JSON serializerが:

```text
TypeError: Object of type UUID is not JSON serializable
```

で停止する。

今回 `json_safe()` を追加し、

```text
UUID     → str
datetime → ISO 8601 string
```

へ再帰的に変換してからJSONBへ保存する。

## 実行

上書き後:

```powershell
cd C:\FLAMORIS\flamoris_ai\apps\umeko_chat
.\.venv\Scripts\Activate.ps1
python chat.py
```

正常なら:

```text
梅子を起動しました。終了は /bye
conversation_id = ...
instance_id     = ...
前回conversationを読み込みました: ... (... messages)
愛乃>
```

となる。

DB Schema変更は不要。
