#!/usr/bin/env bash
# Stop 훅 — 방금 끝난 턴까지 색인한다. 출력 없음, 항상 exit 0.
TC="${TIMECAPSULE_BIN:-$(command -v timecapsule 2>/dev/null)}"
[ -x "$TC" ] || exit 0
"$TC" index --timeout 8 --quiet >/dev/null 2>&1 || true
exit 0
