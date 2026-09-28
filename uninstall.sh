#!/usr/bin/env bash
# 설치 되돌리기. 색인 DB(~/.timecapsule)는 --purge 를 줄 때만 지운다.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETTINGS="$HOME/.claude/settings.json"
DESKTOP="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
STAMP=$(date +%Y%m%d-%H%M%S)
[ -L "$HOME/.local/bin/timecapsule" ] && rm "$HOME/.local/bin/timecapsule"
[ -L "$HOME/.claude/skills/timecapsule" ] && rm "$HOME/.claude/skills/timecapsule"
if command -v jq >/dev/null; then
  if [ -f "$SETTINGS" ] && jq -e '.hooks' "$SETTINGS" >/dev/null; then
    T=$(mktemp "$HOME/.claude/settings.XXXXXX")
    jq --arg here "$HERE/hooks/" '
      .hooks |= (with_entries(.value |= map(select((.hooks // []) | map(.command) | any(startswith("bash " + $here)) | not)))
                 | with_entries(select(.value | length > 0)))
    ' "$SETTINGS" > "$T" && cp "$SETTINGS" "$SETTINGS.bak-timecapsule-$STAMP" && mv "$T" "$SETTINGS"
  fi
  if [ -f "$DESKTOP" ] && jq -e '.mcpServers.timecapsule' "$DESKTOP" >/dev/null; then
    T=$(mktemp "$(dirname "$DESKTOP")/.tc.XXXXXX")
    jq 'del(.mcpServers.timecapsule)' "$DESKTOP" > "$T" && cp "$DESKTOP" "$DESKTOP.bak-timecapsule-$STAMP" && mv "$T" "$DESKTOP"
    echo "데스크톱 MCP 제거 — 앱을 다시 켜야 반영된다"
  fi
fi
[ "${1:-}" = "--purge" ] && rm -rf "$HOME/.timecapsule" && echo "색인 삭제"
echo "제거 완료"
