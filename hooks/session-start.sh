#!/usr/bin/env bash
# SessionStart 훅 — 짧게 증분 색인한 뒤 이 프로젝트를 다룬 최근 세션 요약을 컨텍스트에 넣는다.
# 훅 입력(stdin JSON)의 cwd·session_id 를 엔진이 읽는다 — 이어 열기·압축 때 지금 세션 자신은 빠진다.
# 어떤 경우에도 세션을 막지 않는다(exit 0). 엔진을 못 찾으면 조용히 끝난다.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TC="${TIMECAPSULE_BIN:-$(command -v timecapsule 2>/dev/null)}"
[ -x "$TC" ] || TC="$HERE/../bin/timecapsule"
[ -x "$TC" ] || exit 0
"$TC" hook session-start 2>/dev/null || true
exit 0
