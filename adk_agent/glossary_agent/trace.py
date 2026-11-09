"""ADK 版エージェントに質問し、ツール呼び出しと回答を表示する（演習の --trace に相当）。

使い方（リポジトリの直下で）:
    uv run python -m adk_agent.glossary_agent.trace
"""

import asyncio

from google.adk.runners import InMemoryRunner

from adk_agent.glossary_agent.agent import root_agent


async def main():
    runner = InMemoryRunner(agent=root_agent)
    events = await runner.run_debug("LoRAとQLoRAの違いは？", quiet=True)
    for e in events:
        for c in e.get_function_calls():
            print("[tool call]", c.name, c.args)
        for r in e.get_function_responses():
            print("[tool return]", r.name, str(r.response)[:80])
        if e.is_final_response() and e.content and e.content.parts:
            print(e.content.parts[0].text)


if __name__ == "__main__":
    asyncio.run(main())
