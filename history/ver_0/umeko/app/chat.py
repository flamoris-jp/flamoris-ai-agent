import requests
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "umeko"

# chat.py は C:\FLAMORIS\ai\umeko\app\ に置く想定。
# 1階層上の umeko フォルダから設定Markdownを読む。
BASE_DIR = Path(__file__).resolve().parent.parent


def load_text(filename: str) -> str:
    path = BASE_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {path}")

    return path.read_text(encoding="utf-8")


def build_system_prompt() -> str:
    personality = load_text("personality.md")
    flamoris = load_text("flamoris.md")
    characters = load_text("characters.md")

    return f"""# 梅子 system context

以下の設定・知識を、この会話で最優先の前提として扱ってください。

## Personality

{personality}

## FLAMORIS

{flamoris}

## Characters

{characters}

## Final rules

- 上記に書かれていない事実を、知っているように補完しないでください。
- 未設定の情報は、自然に「まだ知らない」と答えてください。
- 創作案を出す場合は、既存設定ではなく提案だと分かるようにしてください。
"""


system_prompt = build_system_prompt()

messages = [
    {
        "role": "system",
        "content": system_prompt
    }
]

print("梅子を起動しました。終了は /bye")

while True:
    user_text = input("愛乃> ").strip()

    if not user_text:
        continue

    if user_text == "/bye":
        print("梅子> またね。")
        break

    messages.append({
        "role": "user",
        "content": user_text
    })

    try:
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
        data = response.json()
        assistant_text = data["message"]["content"]

    except requests.RequestException as exc:
        print(f"梅子> Ollamaとの通信でエラーが起きたよ: {exc}")
        messages.pop()
        continue

    except (KeyError, TypeError, ValueError) as exc:
        print(f"梅子> Ollamaの返答を読み取れなかったよ: {exc}")
        messages.pop()
        continue

    messages.append({
        "role": "assistant",
        "content": assistant_text
    })

    print(f"梅子> {assistant_text}")
