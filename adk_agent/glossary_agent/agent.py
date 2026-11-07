"""第3回 宿題 発展（a）: 演習の学習支援エージェントを Google ADK で組み立て直す。

使い方（リポジトリの直下で）:
    PYTHONPATH=. uv run --with google-adk adk run adk_agent/glossary_agent

指示（INSTRUCTIONS）とツール（app/tools.py）は演習の Pydantic AI 版をそのまま使い、
エージェントを組み立てる部分だけを書き直している。
"""

from google.adk.agents import Agent

from app import tools
from app.agent import INSTRUCTIONS
from app.config import MODEL

# Pydantic AI 版と同じく、ツールは普通の関数をそのまま渡す（docstring と型ヒントがツールの説明になる）
root_agent = Agent(
    model=MODEL,
    name="glossary_agent",
    instruction=INSTRUCTIONS,
    tools=[tools.search_glossary, tools.get_lecture_summary, tools.make_quiz],
)
