#!/usr/bin/env bash
# 설치 되돌리기. 색인 DB(~/.timecapsule)는 --purge 를 줄 때만 지운다.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETTINGS="$HOME/.claude/settings.json"
[ -L "$HOME/.local/bin/timecapsule" ] && rm "$HOME/.local/bin/timecapsule"
[ -L "$HOME/.claude/skills/timecapsule" ] && rm "$HOME/.claude/skills/timecapsule"
if [ -f "$SETTINGS" ] && command -v jq >/dev/null; then
  T=$(mktemp "$HOME/.claude/settings.XXXXXX")
  jq --arg here "$HERE/hooks/" '
    .hooks |= with_entries(.value |= map(select((.hooks // []) | map(.command) | any(startswith("bash " + $here)) | not)))
  ' "$SETTINGS" > "$T" && mv "$T" "$SETTINGS"
fi
[ "${1:-}" = "--purge" ] && rm -rf "$HOME/.timecapsule" && echo "색인 삭제"
echo "제거 완료"
