# claude-timecapsule

Claude Code 용 로컬 세션 메모리. 데몬·외부 추론 없이 세션 기록을 SQLite FTS5 에 색인하고, 세션 시작 때 최근 맥락을 넣어 주며, 언제든 `timecapsule search` 로 되찾는다. claude-mem 의 대체물이다.

- 원천: `~/.claude/projects/*/*.jsonl` + `~/.codex/sessions/**/*.jsonl` (Codex 기록도 함께 색인)
- 저장: `~/.timecapsule/index.db` — 증분 색인, 파일별 오프셋 기억
- 검색: trigram 토크나이저 (한국어 부분 일치)
- 주입: SessionStart 훅이 현재 프로젝트 최근 세션 5개 요약(≤3k자)을 넣는다
- 실패 처리: CLI 는 실패 시 exit 1(stderr 한 줄), 훅은 자체 fail-open — 세션을 막지 않는다. 예산 초과 시 부분 결과 유지
- 비밀값: AWS 키·토큰·Bearer·JWT·password= 패턴은 색인 시 마스킹

## 설치

```
./install.sh        # 심링크 + 훅 등록 + 첫 색인
./uninstall.sh      # 되돌리기 (--purge 면 색인도 삭제)
timecapsule migrate-claude-mem   # 옛 claude-mem 관찰 가져오기 (선택)
```

Codex 쪽 짝은 [codex-timecapsule](../codex-timecapsule) — 같은 엔진, 같은 DB 를 쓴다.

## 구성

```
SKILL.md            Claude Code 스킬 (~/.claude/skills/timecapsule 로 심링크)
bin/timecapsule     엔진 (python3 표준 라이브러리, 파일 하나)
hooks/session-start.sh · hooks/stop.sh
references/format.md · references/migrate-claude-mem.md
```
