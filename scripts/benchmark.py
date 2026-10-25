"""複数のモデル × 複数の質問で、応答時間とトークン数を計測する。

使い方:
    uv run python scripts/benchmark.py --dry-run      # APIを呼ばずに計測計画だけ表示する
    uv run python scripts/benchmark.py                # 計測して benchmark_results.csv に保存する
    uv run python scripts/benchmark.py --repeat 3 --models gemini-3.5-flash-lite

質問は data/benchmark_questions.json から読み込む。会話履歴は使わず、1問ずつ独立に
送るので、どのモデルも同じ条件（同じ入力）で比べられる。時間帯による混み具合の差が
特定のモデルに偏らないよう、1つの質問を全モデルに続けて送ってから次の質問に進む。

無料枠にはレート制限があるので、呼び出しの間に --interval 秒（既定 5 秒）待つ。
エラーになった呼び出しも CSV に記録し、計測は止めずに続ける。
"""

import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

from google import genai
from google.genai import errors, types

# scripts/ から直接実行しても app パッケージを import できるようにする
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import api_error_message, get_api_key

QUESTIONS = ROOT / "data" / "benchmark_questions.json"
DEFAULT_MODELS = ["gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

FIELDS = [
    "model",
    "question_id",
    "category",
    "trial",
    "elapsed_sec",
    "input_tokens",
    "output_tokens",
    "thought_tokens",
    "answer_chars",
    "error",
]


def load_questions(path: Path = QUESTIONS) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["questions"]


def token_counts(usage: types.GenerateContentResponseUsageMetadata | None) -> dict:
    """入力・出力・思考トークン数を取り出す。出力には思考トークンも含める（ask.py と同じ数え方）。"""
    if usage is None:
        return {"input_tokens": None, "output_tokens": None, "thought_tokens": None}
    thoughts = usage.thoughts_token_count or 0
    return {
        "input_tokens": usage.prompt_token_count or 0,
        "output_tokens": (usage.candidates_token_count or 0) + thoughts,
        "thought_tokens": thoughts,
    }


def measure(client: genai.Client, model: str, question: dict, trial: int) -> dict:
    """1回だけ質問を送り、応答時間とトークン数を1行分の dict にする。"""
    row = {
        "model": model,
        "question_id": question["id"],
        "category": question["category"],
        "trial": trial,
        "elapsed_sec": None,
        "input_tokens": None,
        "output_tokens": None,
        "thought_tokens": None,
        "answer_chars": None,
        "error": "",
    }
    start = time.perf_counter()
    try:
        response = client.models.generate_content(
            model=model, contents=question["question"]
        )
    except errors.APIError as e:
        row["error"] = api_error_message(e.code, e.message)
        return row
    row["elapsed_sec"] = round(time.perf_counter() - start, 3)
    row.update(token_counts(response.usage_metadata))
    row["answer_chars"] = len(response.text or "")
    return row


def summarize(rows: list[dict]) -> list[dict]:
    """モデルごとに、成功した呼び出しの応答時間・トークン数の平均などをまとめる。"""
    summary = []
    for model in dict.fromkeys(r["model"] for r in rows):
        ok = [r for r in rows if r["model"] == model and not r["error"]]
        failed = sum(1 for r in rows if r["model"] == model and r["error"])
        if not ok:
            summary.append({"model": model, "ok": 0, "failed": failed})
            continue
        times = [r["elapsed_sec"] for r in ok]
        summary.append(
            {
                "model": model,
                "ok": len(ok),
                "failed": failed,
                "mean_sec": statistics.mean(times),
                "median_sec": statistics.median(times),
                "max_sec": max(times),
                "mean_input": statistics.mean(r["input_tokens"] for r in ok),
                "mean_output": statistics.mean(r["output_tokens"] for r in ok),
                "mean_thought": statistics.mean(r["thought_tokens"] for r in ok),
            }
        )
    return summary


def print_summary(summary: list[dict]) -> None:
    print("\n=== モデルごとのまとめ（成功した呼び出しのみ） ===")
    print(
        f"{'model':<24} {'成功':>4} {'失敗':>4} {'平均秒':>7} {'中央秒':>7} {'最大秒':>7} "
        f"{'入力':>6} {'出力':>6} {'思考':>6}"
    )
    for s in summary:
        if not s["ok"]:
            print(f"{s['model']:<24} {0:>4} {s['failed']:>4}  （成功なし）")
            continue
        print(
            f"{s['model']:<24} {s['ok']:>4} {s['failed']:>4} "
            f"{s['mean_sec']:>7.2f} {s['median_sec']:>7.2f} {s['max_sec']:>7.2f} "
            f"{s['mean_input']:>6.0f} {s['mean_output']:>6.0f} {s['mean_thought']:>6.0f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="複数モデルの応答時間・トークン数を計測する"
    )
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--repeat", type=int, default=1, help="各質問を何回ずつ送るか")
    parser.add_argument(
        "--interval", type=float, default=5.0, help="呼び出しの間に待つ秒数"
    )
    parser.add_argument("--out", type=Path, default=Path("benchmark_results.csv"))
    parser.add_argument(
        "--dry-run", action="store_true", help="APIを呼ばずに計画だけ表示する"
    )
    args = parser.parse_args()

    questions = load_questions()
    total = len(args.models) * len(questions) * args.repeat
    print(f"[models] {', '.join(args.models)}")
    print(
        f"[plan] {len(questions)} 問 × {len(args.models)} モデル × {args.repeat} 回 = {total} 回の呼び出し"
        f"（間隔 {args.interval} 秒、待ち時間だけで約 {total * args.interval / 60:.1f} 分）"
    )
    if args.dry_run:
        for q in questions:
            print(f"  {q['id']} [{q['category']}] {q['question'].splitlines()[0]}")
        return

    rows = []
    done = 0
    with (
        genai.Client(api_key=get_api_key()) as client,
        args.out.open("w", newline="", encoding="utf-8") as f,
    ):
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for trial in range(1, args.repeat + 1):
            for q in questions:
                for model in args.models:
                    if done:
                        time.sleep(args.interval)
                    row = measure(client, model, q, trial)
                    done += 1
                    rows.append(row)
                    # 途中で止めても、そこまでの結果が残るよう1行ずつ書き出す
                    writer.writerow(row)
                    f.flush()
                    status = row["error"] or (
                        f"{row['elapsed_sec']:.2f} 秒 / 入力 {row['input_tokens']} / 出力 {row['output_tokens']}"
                    )
                    print(f"[{done}/{total}] {model} {q['id']} (試行{trial}): {status}")

    print_summary(summarize(rows))
    print(f"\n[saved] {args.out}")


if __name__ == "__main__":
    main()
