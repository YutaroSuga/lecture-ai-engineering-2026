"""ask.py のテスト。

genai.Client を偽物に差し替えるので、実際のLLMは呼ばない。
APIキーも利用枠も使わずに、「会話履歴を保ったまま続けて質問できるか」と
「エラー時に日本語の説明を出すか」を確かめられる。
"""

import sys
from types import SimpleNamespace

import pytest
from google.genai import errors

from app import ask as ask_module
from app.config import MODEL


class FakeChat:
    """send_message のたびに履歴を積み上げる偽のチャット。"""

    # 先頭から順に、send_message で投げる例外（None なら成功）。テストで差し替える
    initial_errors = ()

    def __init__(self, model):
        self.model = model
        self.history = []
        self.errors = list(self.initial_errors)

    def send_message(self, message):
        error = self.errors.pop(0) if self.errors else None
        if error:
            raise error
        answer = f"回答{len(self.history) + 1}: {message}"
        self.history.append((message, answer))
        usage = SimpleNamespace(
            prompt_token_count=10 * len(self.history),
            candidates_token_count=5,
            thoughts_token_count=None,
        )
        return SimpleNamespace(text=answer, usage_metadata=usage)


class FakeChats:
    def __init__(self):
        self.created = []

    def create(self, model):
        chat = FakeChat(model)
        self.created.append(chat)
        return chat


class FakeClient:
    """genai.Client の偽物。with で使われ、抜けると closed になる。"""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.chats = FakeChats()
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


@pytest.fixture
def fake_client(monkeypatch):
    """genai.Client を偽物に差し替え、main() が作った FakeClient を後から参照できるようにする。"""
    created = []

    def make_client(**kwargs):
        client = FakeClient(**kwargs)
        created.append(client)
        return client

    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key")
    monkeypatch.setattr(ask_module.genai, "Client", make_client)
    return lambda: created[-1]


def run_main(monkeypatch, argv, inputs):
    """argv で main() を起動し、inputs を順に入力する。入力が尽きたら Ctrl+D 扱い。"""
    monkeypatch.setattr(sys, "argv", ["ask", *argv])
    it = iter(inputs)

    def fake_input(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", fake_input)
    ask_module.main()


def test_main_without_api_key_exits(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="GEMINI_API_KEY"):
        run_main(monkeypatch, ["LoRAとは？"], [])


def test_main_prints_question_and_answer(fake_client, monkeypatch, capsys):
    run_main(monkeypatch, ["RAGとは？"], [])

    out = capsys.readouterr().out
    assert f"[model] {MODEL}" in out
    assert "[質問] RAGとは？" in out
    assert "回答1: RAGとは？" in out
    (chat,) = fake_client().chats.created
    assert chat.model == MODEL
    assert fake_client().kwargs == {"api_key": "dummy-key"}


def test_main_uses_default_question(fake_client, monkeypatch):
    run_main(monkeypatch, [], [])

    (chat,) = fake_client().chats.created
    assert chat.history[0][0] == ask_module.DEFAULT_QUESTION


def test_main_keeps_history_across_questions(fake_client, monkeypatch, capsys):
    run_main(monkeypatch, ["LoRAとは？"], ["もっと短く", "exit", "届かない質問"])

    # 1つのチャットに続けて送られ、exit 以降は送られない
    (chat,) = fake_client().chats.created
    assert [q for q, _ in chat.history] == ["LoRAとは？", "もっと短く"]
    assert "回答2: もっと短く" in capsys.readouterr().out


def test_main_closes_client_after_conversation(fake_client, monkeypatch):
    run_main(monkeypatch, ["LoRAとは？"], ["もっと短く"])

    assert fake_client().closed


@pytest.mark.parametrize("word", ["", "exit", "quit", "  QUIT  "])
def test_main_exits_on_exit_words(fake_client, monkeypatch, word):
    run_main(monkeypatch, ["LoRAとは？"], [word, "届かない質問"])

    (chat,) = fake_client().chats.created
    assert len(chat.history) == 1


def test_main_api_error_prints_message_and_continues(fake_client, monkeypatch, capsys):
    error = errors.APIError(429, {"error": {"message": "quota"}})
    monkeypatch.setattr(FakeChat, "initial_errors", (error,))
    run_main(monkeypatch, ["LoRAとは？"], ["もう一度"])

    out = capsys.readouterr().out
    assert "レート制限" in out
    # エラーのあとも会話は続き、次の質問には答える
    (chat,) = fake_client().chats.created
    assert [q for q, _ in chat.history] == ["もう一度"]


def test_main_prints_token_counts(fake_client, monkeypatch, capsys):
    run_main(monkeypatch, ["LoRAとは？"], ["もっと短く"])

    out = capsys.readouterr().out
    # 履歴が積み上がるので、2回目のほうが入力トークン数が多い
    assert "[tokens] 入力: 10 / 出力: 5" in out
    assert "[tokens] 入力: 20 / 出力: 5" in out


def test_main_prints_response_time(fake_client, monkeypatch, capsys):
    # perf_counter を送信前・送信後の順に呼ぶので、差がそのまま応答時間になる
    ticks = iter([100.0, 101.5, 200.0, 200.25])
    monkeypatch.setattr(ask_module.time, "perf_counter", lambda: next(ticks))
    run_main(monkeypatch, ["LoRAとは？"], ["もっと短く"])

    out = capsys.readouterr().out
    assert "[time] 応答時間: 1.50 秒" in out
    assert "[time] 応答時間: 0.25 秒" in out


def test_format_usage_includes_thoughts_in_output():
    usage = SimpleNamespace(
        prompt_token_count=12, candidates_token_count=30, thoughts_token_count=8
    )
    assert (
        ask_module.format_usage(usage) == "[tokens] 入力: 12 / 出力: 38（うち思考: 8）"
    )


def test_format_usage_without_metadata():
    assert ask_module.format_usage(None) == "[tokens] 不明"
