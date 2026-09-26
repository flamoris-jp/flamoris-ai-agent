"""Interactive console over the shared Agent session."""

import asyncio

from flamoris_ai_agent.execution import IntelligenceError
from flamoris_ai_agent.runtime import configured_session


async def run_console():
    session = configured_session()
    try:
        await session.start(load_previous=True)
        print("梅子を起動しました。終了は /bye")
        print(f"conversation_id = {session.conversation_id}")
        print(f"instance_id     = {session.instance_id}")
        if session.previous:
            print(f"前回conversationを読み込みました: {session.previous['conversation_id']}")
        else:
            print("前回conversationはありません。")
        while True:
            text = input("愛乃> ").strip()
            if not text:
                continue
            if text == "/bye":
                print("梅> またね。")
                break
            try:
                result = await session.ask(text)
                print(f"梅> {result.text}")
            except IntelligenceError as exc:
                print(f"梅> 処理に失敗しました: {exc.code}")
                if session.failed:
                    break
    except (KeyboardInterrupt, EOFError, asyncio.CancelledError):
        print("\n梅> 今日はここまでにするね。")
    except IntelligenceError as exc:
        print(f"梅> 起動・保存に失敗しました: {exc.code}")
    finally:
        try:
            await session.aclose()
        except IntelligenceError as exc:
            print(f"梅> 終了処理を確認してください: {exc.code}")


def main():
    asyncio.run(run_console())


if __name__ == "__main__":
    main()
