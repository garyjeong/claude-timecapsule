#!/usr/bin/env bash
# claude-timecapsule 설치 — 심링크 3개 + 훅 2개. 되돌리기는 uninstall.sh
#   ~/.local/bin/timecapsule            → bin/timecapsule
#   ~/.claude/skills/timecapsule        → 이 폴더 (SKILL.md + references)
#   ~/.claude/settings.json hooks       SessionStart / Stop 에 hooks/*.sh 추가 (중복 없이)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETTINGS="$HOME/.claude/settings.json"
command -v jq >/dev/null || { echo "jq 가 필요하다 (brew install jq)"; exit 1; }
command -v python3 >/dev/null || { echo "python3 가 필요하다"; exit 1; }

mkdir -p "$HOME/.local/bin" "$HOME/.claude/skills" "$HOME/.timecapsule"
chmod +x "$HERE/bin/timecapsule" "$HERE"/hooks/*.sh
ln -sfn "$HERE/bin/timecapsule" "$HOME/.local/bin/timecapsule"
ln -sfn "$HERE" "$HOME/.claude/skills/timecapsule"

# 훅 등록 (같은 command 가 이미 있으면 건너뜀)
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
cp "$SETTINGS" "$SETTINGS.bak-timecapsule-$(date +%Y%m%d-%H%M%S)"
T=$(mktemp "$HOME/.claude/settings.XXXXXX")
jq --arg ss "bash $HERE/hooks/session-start.sh" --arg st "bash $HERE/hooks/stop.sh" '
  def add(ev; cmd):
    .hooks[ev] = ((.hooks[ev] // []) as $arr
      | if ($arr | map(.hooks[]?.command) | index(cmd)) then $arr
        else $arr + [{"hooks":[{"type":"command","command":cmd,"timeout":15}]}] end);
  add("SessionStart"; $ss) | add("Stop"; $st)
' "$SETTINGS" > "$T" && mv "$T" "$SETTINGS"

echo "설치 완료"
echo "  bin   : $(readlink "$HOME/.local/bin/timecapsule")"
echo "  skill : $(readlink "$HOME/.claude/skills/timecapsule")"
echo "  hooks : SessionStart · Stop (settings 백업: $SETTINGS.bak-timecapsule-*)"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "  주의  : ~/.local/bin 이 PATH 에 없다";; esac
echo
echo "첫 색인(수십 초)을 지금 돌린다 …"
"$HERE/bin/timecapsule" index --timeout 120
"$HERE/bin/timecapsule" stats
