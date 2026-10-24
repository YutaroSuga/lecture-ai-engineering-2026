"""ask.py のテスト。

genai.Client を偽物に差し替えるので、実際のLLMは呼ばない。
APIキーも利用枠も使わずに、「質問がモデルに渡り、回答が返るか」と
「エラー時に日本語の説明を出して終了するか」を確かめられる。
"""

import sys
from types import SimpleNamespace

import pytest
from google.genai import errors

from app import ask as ask_module
from app.config import MODEL


class FakeModels:
    def __init__(self, text="ダミーの回答", error=None):
        self.text = text
        self.error = error
        self.calls = []

    def generate_content(self, model, contents):
        self.calls.append({"model": model, "contents": contents})
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text)


@pytest.fixture
def fake_models(monkeypatch):
    """genai.Client を偽物に差し替え、呼び出し内容を記録する FakeModels を返す。"""
    models = FakeModels()
    client_kwargs = {}

    def fake_client(**kwargs):
        client_kwargs.update(kwargs)
        return SimpleNamespace(models=models)

    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key")
    monkeypatch.setattr(ask_module.genai, "Client", fake_client)
    models.client_kwargs = client_kwargs
    return models


def test_ask_sends_question_and_returns_text(fake_models):
    answer = ask_module.ask("LoRAとは何ですか？")

    assert answer == "ダミーの回答"
    assert fake_models.calls == [{"model": MODEL, "contents": "LoRAとは何ですか？"}]
    assert fake_models.client_kwargs == {"api_key": "dummy-key"}


def test_ask_without_api_key_exits(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="GEMINI_API_KEY"):
        ask_module.ask("LoRAとは？")


def test_main_prints_question_and_answer(fake_models, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["ask", "RAGとは？"])
    ask_module.main()

    out = capsys.readouterr().out
    assert f"[model] {MODEL}" in out
    assert "[質問] RAGとは？" in out
    assert "ダミーの回答" in out
    assert fake_models.calls[0]["contents"] == "RAGとは？"


def test_main_uses_default_question(fake_models, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["ask"])
    ask_module.main()

    assert fake_models.calls[0]["contents"] == ask_module.DEFAULT_QUESTION


def test_main_api_error_prints_message_and_exits(fake_models, monkeypatch, capsys):
    fake_models.error = errors.APIError(429, {"error": {"message": "quota"}})
    monkeypatch.setattr(sys, "argv", ["ask", "LoRAとは？"])

    with pytest.raises(SystemExit) as exc_info:
        ask_module.main()

    assert exc_info.value.code == 1
    assert "レート制限" in capsys.readouterr().out
