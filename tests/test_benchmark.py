"""scripts/benchmark.py のテスト。

genai.Client を偽物に差し替えるので、実際のLLMは呼ばない。
"""

from types import SimpleNamespace

from google.genai import errors

from scripts import benchmark


class FakeModels:
    def __init__(self, fail_models=()):
        self.fail_models = set(fail_models)
        self.calls = []

    def generate_content(self, model, contents):
        self.calls.append((model, contents))
        if model in self.fail_models:
            raise errors.APIError(429, {"error": {"message": "quota"}})
        usage = SimpleNamespace(prompt_token_count=10, candidates_token_count=20, thoughts_token_count=5)
        return SimpleNamespace(text="こたえ", usage_metadata=usage)


QUESTION = {"id": "q01", "category": "短答", "question": "質問"}


def test_questions_file_has_ten_unique_questions():
    questions = benchmark.load_questions()
    assert len(questions) == 10
    assert len({q["id"] for q in questions}) == 10
    assert all(q["question"] and q["category"] for q in questions)


def test_measure_records_time_and_tokens():
    client = SimpleNamespace(models=FakeModels())
    row = benchmark.measure(client, "m1", QUESTION, trial=1)
    assert row["error"] == ""
    assert row["elapsed_sec"] >= 0
    # 出力には思考トークンも含める
    assert (row["input_tokens"], row["output_tokens"], row["thought_tokens"]) == (10, 25, 5)
    assert row["answer_chars"] == 3
    assert set(row) == set(benchmark.FIELDS)


def test_measure_records_error_without_raising():
    client = SimpleNamespace(models=FakeModels(fail_models={"m1"}))
    row = benchmark.measure(client, "m1", QUESTION, trial=1)
    assert "レート制限" in row["error"]
    assert row["elapsed_sec"] is None


def test_summarize_ignores_failed_calls():
    rows = [
        {"model": "m1", "error": "", "elapsed_sec": 1.0, "input_tokens": 10, "output_tokens": 20, "thought_tokens": 0},
        {"model": "m1", "error": "", "elapsed_sec": 3.0, "input_tokens": 30, "output_tokens": 40, "thought_tokens": 2},
        {"model": "m1", "error": "x", "elapsed_sec": None, "input_tokens": None, "output_tokens": None,
         "thought_tokens": None},
        {"model": "m2", "error": "x", "elapsed_sec": None, "input_tokens": None, "output_tokens": None,
         "thought_tokens": None},
    ]
    m1, m2 = benchmark.summarize(rows)
    assert (m1["ok"], m1["failed"], m1["mean_sec"], m1["mean_output"]) == (2, 1, 2.0, 30)
    assert (m2["model"], m2["ok"], m2["failed"]) == ("m2", 0, 1)
