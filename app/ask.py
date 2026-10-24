"""第1回: 素のLLMに質問するスクリプト（会話履歴つき）。

使い方:
    uv run python -m app.ask "LoRAとは何ですか？"
    uv run python -m app.ask            # 質問を省略すると、講座に固有の質問をする

最初の質問に答えたあと、続けて質問できる。会話履歴は保たれるので、
「さっきの答えをもっと短く」のように前の発言を踏まえた質問もできる。
空行・exit・quit・Ctrl+D で終了する。

回答のあとに、その回の入力・出力トークン数を表示する。会話履歴も毎回まとめて
送られるので、質問を重ねるほど入力トークン数が増えていくことを確かめよう。

ツールは持たない「素の」呼び出し。
講座に固有のことを聞くと、「分からない」と答えるか、一般論でもっともらしく答える
（講座の実際とは違う）ことを確かめよう。
（第3回で、用語集を検索できるエージェントにして改善する）
"""

import argparse

from google import genai
from google.genai import chats, errors, types

from app.config import MODEL, api_error_message, get_api_key

# 講座に固有の質問。正しい答えは data/glossary.json の homework-levels にある
DEFAULT_QUESTION = "AIE2026の講座の宿題にある「3レベル」とは何ですか？"

EXIT_WORDS = {"", "exit", "quit"}


def start_chat(client: genai.Client) -> chats.Chat:
    """会話履歴を保つチャットを始める。send_message するたびに履歴が積み上がる。

    Chat は client への参照を持たない。client が破棄されると通信が閉じられ、
    以降の send_message が失敗するので、会話が終わるまで client を保持すること。
    """
    return client.chats.create(model=MODEL)


def format_usage(usage: types.GenerateContentResponseUsageMetadata | None) -> str:
    """回答1回分の入力・出力トークン数を1行にまとめる。

    思考（thinking）トークンも出力として課金されるので、出力に含めて内訳を添える。
    """
    if usage is None:
        return "[tokens] 不明"
    prompt = usage.prompt_token_count or 0
    thoughts = usage.thoughts_token_count or 0
    output = (usage.candidates_token_count or 0) + thoughts
    line = f"[tokens] 入力: {prompt} / 出力: {output}"
    if thoughts:
        line += f"（うち思考: {thoughts}）"
    return line


def main() -> None:
    parser = argparse.ArgumentParser(description="素のLLMに質問する（会話履歴つき）")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    args = parser.parse_args()

    print(f"[model] {MODEL}")
    print("（続けて質問できます。空行・exit・quit・Ctrl+D で終了）")
    with genai.Client(api_key=get_api_key()) as client:
        chat = start_chat(client)

        question = args.question
        print(f"[質問] {question}\n")
        while True:
            try:
                response = chat.send_message(question)
                print(response.text)
                print(f"\n{format_usage(response.usage_metadata)}")
            except errors.APIError as e:
                # 一時的なエラーもあるので、会話は終わらせずに次の質問を受け付ける
                print(api_error_message(e.code, e.message))

            try:
                question = input("\n[質問] ").strip()
            except EOFError:
                print()
                break
            if question.lower() in EXIT_WORDS:
                break
            print()


if __name__ == "__main__":
    main()
