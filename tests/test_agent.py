"""エージェントの配線テスト。

TestModel は実際のLLMを呼ばない偽モデルで、登録されたツールを全部呼んでから
ダミーの回答を返す。APIキーも利用枠も使わずに、
「ツールが登録され、呼ばれ、結果がモデルに戻るか」を確かめられる。
"""

import pytest
from pydantic_ai import DeferredToolRequests, DeferredToolResults, ToolDenied
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.models.test import TestModel

from app import tools
from app.agent import agent

BASE_TOOLS = {"search_glossary", "get_lecture_summary"}


def _parts(result, kind):
    return [p for m in result.all_messages() for p in m.parts if isinstance(p, kind)]


def test_base_tools_are_registered_and_called():
    model = TestModel()
    with agent.override(model=model):
        result = agent.run_sync("LoRAとは？")

    offered = {t.name for t in model.last_model_request_parameters.function_tools}
    assert BASE_TOOLS <= offered  # 演習でツールを足しても壊れないよう「含む」で判定

    called = {p.tool_name for p in _parts(result, ToolCallPart)}
    assert BASE_TOOLS <= called
    # 承認が必要なツール（requires_approval=True）は、実行されずに承認待ちになるので戻り値が無い
    waiting = len(result.output.approvals) if isinstance(result.output, DeferredToolRequests) else 0
    assert len(_parts(result, ToolReturnPart)) + waiting == len(_parts(result, ToolCallPart))
    assert result.output


def test_glossary_result_reaches_the_model():
    model = TestModel(call_tools=["search_glossary"])
    with agent.override(model=model):
        result = agent.run_sync("RAGとは？")
    returns = _parts(result, ToolReturnPart)
    assert returns and returns[0].tool_name == "search_glossary"


@pytest.mark.parametrize("approved", [True, False])
def test_save_learning_log_waits_for_approval(tmp_path, monkeypatch, approved):
    """保存は承認待ちで一度止まり、承認したときだけファイルに書かれる。"""
    log_dir = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LOG_DIR", log_dir)
    model = TestModel(call_tools=["save_learning_log"])
    with agent.override(model=model):
        result = agent.run_sync("学習ログに保存して")
        assert isinstance(result.output, DeferredToolRequests)
        [call] = result.output.approvals
        assert call.tool_name == "save_learning_log"
        assert not log_dir.exists()  # 承認前は保存されていない

        decision = True if approved else ToolDenied("利用者が実行を許可しませんでした。")
        result = agent.run_sync(
            message_history=result.all_messages(),
            deferred_tool_results=DeferredToolResults(approvals={call.tool_call_id: decision}),
        )

    assert isinstance(result.output, str)
    [ret] = [p for p in _parts(result, ToolReturnPart) if p.tool_call_id == call.tool_call_id]
    if approved:
        assert "保存しました" in str(ret.content)
        assert len(list(log_dir.glob("*.md"))) == 1
    else:
        assert "許可しませんでした" in str(ret.content)
        assert not log_dir.exists()
