# リポジトリ直下の .env（git 管理外）があれば、その中身を環境変数として読み込む。
# ~/.bashrc から読み込まれる（devcontainer.json の postCreateCommand で登録）。
_aie_env="$(dirname "${BASH_SOURCE[0]}")/../.env"
if [ -f "$_aie_env" ]; then
  set -a
  . <(tr -d '\r' < "$_aie_env")
  set +a
fi
unset _aie_env
