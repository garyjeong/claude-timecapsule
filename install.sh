#!/usr/bin/env bash
# claude-timecapsule 설치 — 심링크 2개 + Claude Code 훅 2개 + Claude 데스크톱 MCP 1개. 되돌리기는 uninstall.sh
#   ~/.local/bin/timecapsule            → bin/timecapsule
#   ~/.claude/skills/timecapsule        → 이 폴더 (SKILL.md + references)
#   ~/.claude/settings.json hooks       SessionStart / UserPromptSubmit / Stop 에 hooks/*.sh (중복 없이)
#   claude_desktop_config.json          mcpServers.timecapsule (데스크톱 채팅용 — 앱을 다시 켜야 잡힌다)
# 훅 명령 문자열은 판이 바뀌어도 그대로다 — 이미 열린 세션도 다음 턴부터 새 엔진을 쓴다.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETTINGS="$HOME/.claude/settings.json"
DESKTOP="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
command -v jq >/dev/null || { echo "jq 가 필요하다 (brew install jq)"; exit 1; }
command -v python3 >/dev/null || { echo "python3 가 필요하다"; exit 1; }
STAMP=$(date +%Y%m%d-%H%M%S)

# 바뀔 때만 백업하고 쓴다
apply_json() {  # $1=파일 $2=jq 필터, 나머지는 jq 인자
  local file="$1" filter="$2"; shift 2
  local tmp; tmp=$(mktemp "$(dirname "$file")/.tc.XXXXXX")
  # jq 가 실패하거나 빈 결과를 내면 원본을 건드리지 않고 멈춘다 (if 조건 안이라 set -e 가 듣지 않는다)
  if ! jq "$@" "$filter" "$file" > "$tmp" || ! jq -e 'type == "object"' "$tmp" >/dev/null; then
    rm -f "$tmp"; echo "설정 갱신 실패 — 원본 그대로: $file" >&2; exit 1
  fi
  if cmp -s <(jq -S . "$file") <(jq -S . "$tmp"); then rm -f "$tmp"; return 1; fi
  cp "$file" "$file.bak-timecapsule-$STAMP"
  mv "$tmp" "$file"
}

mkdir -p "$HOME/.local/bin" "$HOME/.claude/skills" "$HOME/.timecapsule"
chmod +x "$HERE/bin/timecapsule" "$HERE"/hooks/*.sh
ln -sfn "$HERE/bin/timecapsule" "$HOME/.local/bin/timecapsule"
ln -sfn "$HERE" "$HOME/.claude/skills/timecapsule"

# Claude Code 훅 (같은 command 가 이미 있으면 건너뜀)
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
if apply_json "$SETTINGS" '
  def add(ev; cmd):
    .hooks[ev] = ((.hooks[ev] // []) as $arr
      | if ($arr | map(.hooks[]?.command) | index(cmd)) then $arr
        else $arr + [{"hooks":[{"type":"command","command":cmd,"timeout":15}]}] end);
  add("SessionStart"; $ss) | add("UserPromptSubmit"; $up) | add("Stop"; $st)' \
  --arg ss "bash $HERE/hooks/session-start.sh" --arg up "bash $HERE/hooks/prompt.sh" --arg st "bash $HERE/hooks/stop.sh"; then
  HOOKS="등록함"; else HOOKS="이미 있음"; fi

# Claude 데스크톱 MCP — GUI 앱은 셸 PATH 를 모르므로 인터프리터를 절대경로로 박는다(brew 의 고정 심링크 우선)
MCP="데스크톱 앱 없음"
if [ -d "$(dirname "$DESKTOP")" ]; then
  PY=""
  for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do [ -x "$c" ] && { PY="$c"; break; }; done
  [ -n "$PY" ] || PY="$(python3 -c 'import sys; print(sys.executable)')"
  [ -f "$DESKTOP" ] || echo '{}' > "$DESKTOP"
  if apply_json "$DESKTOP" '.mcpServers.timecapsule = {"command": $py, "args": [$bin, "mcp"]}' \
    --arg py "$PY" --arg bin "$HOME/.local/bin/timecapsule"; then
    MCP="등록함 — Claude 데스크톱을 완전히 종료했다가 다시 켜야 채팅에서 잡힌다"; else MCP="이미 있음"; fi
fi

echo "설치 완료"
echo "  bin   : $(readlink "$HOME/.local/bin/timecapsule")"
echo "  skill : $(readlink "$HOME/.claude/skills/timecapsule")"
echo "  hooks : SessionStart · UserPromptSubmit · Stop — $HOOKS"
echo "  mcp   : $MCP"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "  주의  : ~/.local/bin 이 PATH 에 없다";; esac
echo
echo "증분 색인 …"
"$HERE/bin/timecapsule" index --timeout 120
"$HERE/bin/timecapsule" doctor
