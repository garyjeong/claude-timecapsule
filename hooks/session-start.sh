#!/usr/bin/env bash
# SessionStart 훅 — 최신 파일부터 4초 예산으로 증분 색인한 뒤, 현재 프로젝트의 최근 세션 요약을 컨텍스트에 넣는다.
# 어떤 경우에도 세션을 막지 않는다(exit 0). timecapsule 이 없으면 조용히 끝난다.
TC="${TIMECAPSULE_BIN:-$(command -v timecapsule 2>/dev/null)}"
[ -x "$TC" ] || exit 0
PROJECT="${CLAUDE_PROJECT_DIR:-$PWD}"
"$TC" index --quick --quiet >/dev/null 2>&1 || true
"$TC" recent --project "$PROJECT" --limit "${TIMECAPSULE_RECENT_LIMIT:-5}" --max-chars "${TIMECAPSULE_RECENT_CHARS:-3000}" 2>/dev/null || true
exit 0
