"""Interactive console over the shared Agent session."""

import asyncio

from flamoris_ai_agent.execution import IntelligenceError
from flamoris_ai_agent.runtime import configured_session


async def run_console():
    session = configured_session()
    try:
        await session.start(load_previous=True)
        print("Agent started. Use /bye to exit.")
        print(f"conversation_id = {session.conversation_id}")
        print(f"instance_id     = {session.instance_id}")
        if session.previous:
            print(f"Previous conversation loaded: {session.previous['conversation_id']}")
        else:
            print("No previous conversation.")
        while True:
            text = input("You> ").strip()
            if not text:
                continue
            if text == "/bye":
                print("Agent> Goodbye.")
                break
            try:
                result = await session.ask(text)
                print(f"Agent> {result.text}")
            except IntelligenceError as exc:
                print(f"Agent> Request failed: {exc.code}")
                if session.failed:
                    break
    except (KeyboardInterrupt, EOFError, asyncio.CancelledError):
        print("\nAgent> Session interrupted.")
    except IntelligenceError as exc:
        print(f"Agent> Startup or persistence failed: {exc.code}")
    finally:
        try:
            await session.aclose()
        except IntelligenceError as exc:
            print(f"Agent> Shutdown requires attention: {exc.code}")


def main():
    asyncio.run(run_console())


if __name__ == "__main__":
    main()
