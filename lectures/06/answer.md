# 第6回 解答

## 演習

<!-- [tool call] の行は、表示された行をそのまま貼り付けてください。終わらなかった STEP は、空欄のままでかまいません。 -->

- STEP 1 のツールの名前：glossary_search_glossary
- STEP 2 の [tool call]：[tool call]   glossary_search_glossary({'query': '3レベル'})
- STEP 3 の [tool call]：[tool call]   fetch_fetch({'url': 'https://modelcontextprotocol.io/'})
- STEP 4 の [tool call]：
    1. [tool call]   aws_aws___search_documentation({'search_phrase': 'Amazon S3 バージョニング 概要'})
    2. [tool call]   aws_aws___search_documentation({'search_phrase': '"Versioning" site:docs.aws.amazon.com/AmazonS3/latest/userguide'})
- 気づき・疑問：
    - 気づき：STEP 4 では、ツールが 2 回呼ばれた。1 回目は日本語の検索語、2 回目は英語の `"Versioning"` に `site:` を付けた検索語だった。1 回目の結果が足りないと判断して、モデルが自分で検索語を変えて呼び直したように見える。どのツールを何回呼ぶかは、モデルが決めていることが分かった
    - 気づき：設定ファイルに数行足すだけで、エージェントのコードを変えずにツールが増えた。その分、出所の分からないサーバーを足すと、説明文や返す内容がそのままモデルに渡るので、足す前の確認が大事だと感じた

## 宿題

<!-- 基礎・実装・発展のどれか1つに取り組めば完了です。 -->

- 取り組んだレベル：発展（調べたソフトウェア：Claude Code）
- 調べた日付：2026-11-28（手元で確かめた版：Claude Code 2.1.332、VS Code 拡張に入っているもの）
- 参照した公式ドキュメント：
  - Connect Claude Code to tools via MCP: https://code.claude.com/docs/en/mcp
  - 組織で MCP サーバーを管理する設定（managed-mcp.json）: https://code.claude.com/docs/en/managed-mcp
- やったこと：
  1. 公式ドキュメントで、4 つの項目（設定を書く場所・コマンドで起動する書き方・URL で接続する書き方・有効になる範囲）を調べた
  2. 空の作業フォルダに、演習の `app/mcp_servers.json` をそのまま `.mcp.json` という名前で置き、`claude mcp list` で読ませた
  3. 別の作業フォルダで、演習と同じ 3 つのサーバー（glossary・fetch・aws）を `claude mcp add` で登録し、書き出された JSON を演習の設定と比べた
  4. 同じ 3 つをローカルの範囲にも登録し、`claude mcp list` で接続を確認したあと、`claude -p` で用語集のツールを呼ばせて、ツールの名前を確かめた。確認後、ローカルの登録は `claude mcp remove` で消した

### 調べた結果：演習の `app/mcp_servers.json` との比較

| 調べること | 演習（`app/mcp_servers.json`） | Claude Code |
|---|---|---|
| 設定を書く場所 | `app/mcp_servers.json` の 1 つだけ。`app/mcp_agent.py` がこのファイルを読む | 範囲ごとに場所が違う。プロジェクト：プロジェクトの一番上の `.mcp.json`。ローカルとユーザー：`~/.claude.json`。ファイルを手で書くほか、`claude mcp add`（または `claude mcp add-json`）コマンドで登録でき、`claude mcp list` / `get` / `remove`、会話の中の `/mcp` で確認・削除できる。組織の管理者用に `/etc/claude-code/managed-mcp.json`（Linux）もある |
| コマンドで起動する書き方 | `"command"` と `"args"`。`"command"` があれば stdio で起動する | `"type": "stdio"`、`"command"`、`"args"`、`"env"`。コマンドでは `claude mcp add --transport stdio glossary -- uv run python -m app.mcp_server` のように、`--` のあとに起動するコマンドを書く（`--` より前は Claude Code のオプション、後ろはそのままサーバーに渡る） |
| URL で接続する書き方 | `"url"` だけ。`"url"` があれば Streamable HTTP で接続する | `"type": "http"` と `"url"`（必要なら `"headers"`）。コマンドでは `claude mcp add --transport http aws https://knowledge-mcp.global.api.aws`。`"type"` には `sse`（非推奨）と `ws` も書ける。ログインが必要なサーバーは `/mcp` からブラウザで OAuth 認証する |
| 有効になる範囲 | このリポジトリの `app/mcp_agent.py` を実行したときだけ | 3 つから選ぶ。ローカル（既定）：そのプロジェクトだけ・自分だけ。プロジェクト：そのプロジェクトだけ・`.mcp.json` を Git に入れてチームと共有。ユーザー：自分のすべてのプロジェクト。同じ名前が複数の範囲にあると、ローカル → プロジェクト → ユーザーの順に優先し、項目は混ぜずに 1 つの定義だけを使う |

### 手元で確かめた結果

- 演習の設定をそのまま `.mcp.json` にすると、`aws` だけが読み飛ばされた。glossary と fetch は読み込まれた

  ```text
  glossary: uv run python -m app.mcp_server - ⏸ Pending approval (run `claude` to approve)
  fetch: uvx mcp-server-fetch==2026.11.11 --no-readability-js - ⏸ Pending approval (run `claude` to approve)
   └ [Warning] [aws] mcpServers.aws: Skipped — MCP server "aws" has a "url" but no "type"; add "type": "http" (or "sse" / "ws") to this entry
  ```

  演習のエージェントは「`url` というキーがあるか」で接続のしかたを決める。Claude Code は `"type"` で決め、`"type"` がないものは stdio として読む。そのため、`"url"` だけでは設定の誤りになる
- プロジェクトの `.mcp.json` に書いたサーバーは「Pending approval」（承認待ち）になり、すぐには接続しなかった。公式ドキュメントにも、対話のセッションでは使う前に承認を求める、と書かれている。Git で受け取った `.mcp.json` のコマンドが勝手に動かないようにするためだと思う
- `claude mcp add --scope project` で登録すると、次の `.mcp.json` が書き出された（glossary は作業フォルダの外にあるリポジトリで動かすため、`uv --directory` を付けた）。どのサーバーにも `"type"` が書かれる

  ```json
  {
    "mcpServers": {
      "glossary": {
        "type": "stdio",
        "command": "uv",
        "args": ["--directory", "/workspaces/lecture-ai-engineering-2026", "run", "python", "-m", "app.mcp_server"],
        "env": {}
      },
      "fetch": {
        "type": "stdio",
        "command": "uvx",
        "args": ["mcp-server-fetch==2026.11.11", "--no-readability-js"],
        "env": {}
      },
      "aws": {
        "type": "http",
        "url": "https://knowledge-mcp.global.api.aws"
      }
    }
  }
  ```

- 同じ名前でローカルにも登録すると、`claude mcp get aws` の `Scope` は `Local config (private to you in this project)` になり、ローカルが優先された。`claude mcp list` では 3 つとも `✔ Connected` になった
- ツールの名前は、演習では「サーバー名 + `_` + ツール名」、Claude Code では「`mcp__` + サーバー名 + `__` + ツール名」だった。どちらも、サーバー名を前に付けて区別するところは同じ

  | サーバー | 演習のツール名 | Claude Code のツール名 |
  |---|---|---|
  | glossary | `glossary_search_glossary` | `mcp__glossary__search_glossary` |
  | fetch | `fetch_fetch` | `mcp__fetch__fetch` |
  | aws | `aws_aws___search_documentation` など | `mcp__aws__aws___search_documentation` など（ほかに `list_regions`・`read_documentation` など計 5 個） |

- Claude Code から用語集のツールを呼ばせると、`mcp__glossary__search_glossary` に `{"query": "LoRA"}` が渡り、演習と同じ用語集の内容が返った。サーバー側（`app/mcp_server.py`）は 1 行も変えていない

### 気づき・疑問

- 気づき：`"mcpServers"` の下にサーバー名を並べ、`command` / `args` / `url` を書く形は、演習と Claude Code で同じだった。そのため、同じ MCP サーバーを、設定を少し書き換えるだけで別のエージェントから使える。違いは主に `"type"` の書き方と、設定を置く場所・範囲だった
- 気づき：演習の設定は、ファイル 1 つで、このリポジトリのエージェントにしか効かない。Claude Code は「自分だけか、チームで共有するか」「このプロジェクトだけか、すべてか」を選べる。そのぶん、プロジェクトの `.mcp.json` には承認が必要で、組織が使えるサーバーを `managed-mcp.json` で絞ることもできる。補足で読んだ「足す前に確認すること」を、ソフトウェアの側でも仕組みとして支えていると感じた
- 気づき：公式ドキュメントには、`.mcp.json` で `${API_KEY}` のように環境変数を使える、とも書かれている。API キーをファイルに直接書かずに、`.mcp.json` を Git で共有できる
- 疑問と確かめたこと：演習のエージェントは `"type"` を読まず、`url` があるかどうかだけで決める。それなら、演習の設定にも `"type"` を書けば、同じ内容を両方で使えるのではないかと考えた。3 つのサーバーに `"type"` を足した設定を一時ファイルに作って演習のエージェントに読ませると、`[server]` の 3 行は同じで、`モデルに見えているツール: 7 個` も変わらなかった。`"type"` を書いておくほうが、ほかのソフトウェアにも持っていきやすい
