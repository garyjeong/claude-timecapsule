#!/usr/bin/env bash
# Stop 훅 — 방금 끝난 턴까지 색인한다. 출력 없음, 항상 exit 0.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TC="${TIMECAPSULE_BIN:-$(command -v timecapsule 2>/dev/null)}"
[ -x "$TC" ] || TC="$HERE/../bin/timecapsule"
[ -x "$TC" ] || exit 0
"$TC" hook stop >/dev/null 2>&1 || true
exit 0
