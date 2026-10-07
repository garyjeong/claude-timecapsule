#!/usr/bin/env bash
# Claude Code UserPromptSubmit 훅 — 그 프롬프트와 닿는 과거 세션을 넣는다. 엔진이 없거나 실패해도 세션을 막지 않는다.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TC="${TIMECAPSULE_BIN:-$(command -v timecapsule 2>/dev/null)}"
[ -x "$TC" ] || TC="$HERE/../bin/timecapsule"
[ -x "$TC" ] || exit 0
"$TC" hook prompt 2>/dev/null || true
exit 0
