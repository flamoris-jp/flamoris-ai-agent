import os
from datetime import date, datetime
from uuid import UUID

from flamoris_ai_agent.config import load_agent_text
from flamoris_ai_agent.db import (
    close_instance,
    close_runtime,
    get_connection,
    get_previous_conversation,
    load_runtime_refs,
    save_message,
    start_conversation,
    start_instance,
    validate_model_ref,
)
from flamoris_ai_agent.intelligence import IntelligenceClient, IntelligenceError

INTELLIGENCE_BASE_URL = os.getenv("INTELLIGENCE_BASE_URL", "http://127.0.0.1:8081")
INTELLIGENCE_MODEL = os.getenv("INTELLIGENCE_MODEL")
MAX_CONTEXT_MESSAGES = int(os.getenv("UMEKO_CONTEXT_MESSAGES", "16"))
PREVIOUS_MESSAGE_LIMIT = int(os.getenv("UMEKO_PREVIOUS_MESSAGES", "12"))
LOAD_PREVIOUS = os.getenv(
    "UMEKO_LOAD_PREVIOUS_CONVERSATION",
    "true",
).lower() in {"1", "true", "yes", "on"}


def json_safe(value):
    """Convert values such as UUID/datetime into JSON-safe representations."""
    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]

    return value


def load_text(filename: str) -> str:
    return load_agent_text(filename)


def load_system_context() -> dict[str, str]:
    return {
        "personality.md": load_text("personality.md"),
        "flamoris.md": load_text("flamoris.md"),
        "characters.md": load_text("characters.md"),
    }


def format_previous_conversation(previous) -> str:
    if not previous or not previous["messages"]:
        return "前回の会話記録はありません。"

    lines = [
        f"conversation_id: {previous['conversation_id']}",
        "",
    ]

    for message in previous["messages"]:
        lines.append(f"{message['sender']}: {message['content']}")

    return "\n".join(lines)


def build_system_prompt(
    context: dict[str, str],
    previous_text: str,
) -> str:
    return f"""# 梅子 system context

以下の設定・知識を、この会話で最優先の前提として扱ってください。

## Personality

{context["personality.md"]}

## FLAMORIS

{context["flamoris.md"]}

## Characters

{context["characters.md"]}

## Previous conversation

以下は、同じAgent・同じProjectで行われた直前の会話ログです。
必要な場合だけ、前回の会話を思い出すための文脈として利用してください。

これは生の会話ログです。
ここに登場する推測・冗談・未確認情報を、
正式なFLAMORIS設定やKnowledgeへ昇格させないでください。

前回conversationは参照資料です。
前回のassistant発言を、現在のユーザー発言として扱わないでください。
前回の質問や提案を、現在も未回答の課題であるかのように引き継がないでください。
現在のユーザー発言に直接必要な情報だけを取り出してください。

{previous_text}

## Final rules

- 上記に書かれていない事実を、知っているように補完しないでください。
- 未設定の情報は、自然に「まだ知らない」と答えてください。
- 創作案を出す場合は、既存設定ではなく提案だと分かるようにしてください。
- 前回会話を毎回話題に出す必要はありません。
- 前回会話は、愛乃が過去の話を参照した場合や、会話の継続に必要な場合だけ使ってください。
"""


def build_messages(
    system_prompt: str,
    history: list[dict],
) -> list[dict]:
    return [
        {
            "role": "system",
            "content": system_prompt,
        },
        *history[-MAX_CONTEXT_MESSAGES:],
    ]


def main():
    base_context = load_system_context()
    history: list[dict] = []

    client = IntelligenceClient(INTELLIGENCE_BASE_URL, INTELLIGENCE_MODEL)
    model = client.resolve_model()

    conn = get_connection()
    instance_id = None
    runtime = None

    try:
        refs = load_runtime_refs(conn)
        validate_model_ref(conn, refs["model_id"], model)

        previous = None

        if LOAD_PREVIOUS:
            previous = get_previous_conversation(
                conn,
                agent_id=refs["agent_id"],
                project_id=refs["project_id"],
                message_limit=PREVIOUS_MESSAGE_LIMIT,
            )

        previous_text = format_previous_conversation(previous)

        # system_context is stored in PostgreSQL JSONB.
        # UUID/datetime values from the previous conversation must be
        # converted before Psycopg's JSON serializer receives them.
        system_context = json_safe(
            {
                **base_context,
                "previous_conversation": previous,
            }
        )

        system_prompt = build_system_prompt(
            base_context,
            previous_text,
        )

        instance_id = start_instance(conn, refs)

        runtime = start_conversation(
            conn,
            refs=refs,
            instance_id=instance_id,
            system_prompt=system_prompt,
            system_context=system_context,
        )

        conversation_id = runtime["conversation_id"]

        print(
            "梅子を起動しました。終了は /bye\n"
            f"conversation_id = {conversation_id}\n"
            f"instance_id     = {instance_id}"
        )

        if previous:
            print(
                "前回conversationを読み込みました: "
                f"{previous['conversation_id']} "
                f"({len(previous['messages'])} messages)"
            )
        else:
            print("前回conversationはありません。")

        while True:
            user_text = input("愛乃> ").strip()

            if not user_text:
                continue

            if user_text == "/bye":
                print("梅> またね。")
                break

            save_message(
                conn,
                conversation_id=conversation_id,
                sender_participant_id=runtime["human_participant_id"],
                role="user",
                content=user_text,
                origin_instance_id=instance_id,
            )

            history.append(
                {
                    "role": "user",
                    "content": user_text,
                }
            )

            try:
                assistant_text = client.chat(
                    model,
                    build_messages(system_prompt, history),
                )
            except IntelligenceError as exc:
                print(f"梅> モデルとの通信でエラーが起きたよ: {exc}")
                continue

            history.append(
                {
                    "role": "assistant",
                    "content": assistant_text,
                }
            )

            save_message(
                conn,
                conversation_id=conversation_id,
                sender_participant_id=runtime["agent_participant_id"],
                role="assistant",
                content=assistant_text,
                origin_instance_id=instance_id,
                metadata={
                    "intelligence_model": model,
                },
            )

            print(f"梅> {assistant_text}")

    except (KeyboardInterrupt, EOFError):
        print("\n梅> 今日はここまでにするね。")

    finally:
        try:
            if instance_id is not None and runtime is not None:
                close_runtime(
                    conn,
                    conversation_id=runtime["conversation_id"],
                    conversation_session_id=runtime["conversation_session_id"],
                    instance_id=instance_id,
                )
            elif instance_id is not None:
                close_instance(conn, instance_id)
        finally:
            conn.close()


if __name__ == "__main__":
    main()
