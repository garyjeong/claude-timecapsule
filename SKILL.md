---
name: timecapsule
description: "Local, daemon-free session memory for Claude Code and Codex. Use when the user asks what was done before, when a past decision or command needs to be recalled (\"지난번에 어떻게 했지\", \"전에 이 오류 봤는데\", \"어느 세션에서\", \"did we already\"), when starting work on a project that has prior sessions, or when claude-mem style recall is needed. Indexes ~/.claude/projects and ~/.codex/sessions into SQLite FTS5 (trigram, Korean-safe) and exposes `timecapsule recent|search|session`. Never treats a past session as current policy — the Obsidian vault stays the source of truth."
---

# /timecapsule

세션 기록(Claude Code · Codex)을 로컬 SQLite 에 색인해 두고 다시 꺼내 쓴다. 데몬도, 외부 추론 호출도 없다.

## 언제 쓰나

- 「지난번에 어떻게 했지」「전에 이 오류 봤는데」「어느 세션에서 바꿨지」 — `search`
- 프로젝트 작업을 시작할 때 최근 흐름 파악 — `recent` (SessionStart 훅이 자동 주입)
- 특정 세션의 전개를 다시 보고 싶을 때 — `session <id>`

## 명령

```
timecapsule recent [--project P] [--limit 5] [--days N] [--max-chars 3000]
timecapsule search "질의" [--project P] [--agent claude|codex|claude-mem] [--role user|assistant|tool] [--days N] [--limit 20]
timecapsule session <id 앞 8자리>
timecapsule tools [--session ID | --days N] [--commands]   # 지난 세션에 무슨 도구·명령을 썼나 (주 에이전트만)
timecapsule index [--quick]          # 훅이 알아서 돌린다. 손으로는 대량 변경 후에만
timecapsule stats · doctor
```

검색은 trigram 이라 한국어 조사·활용이 붙어도 3글자 이상이면 잡힌다. 여러 단어는 AND.

## 규칙

1. **출력 머리의 문구를 지키라.** 세션 기록은 「당시의 판단」이다. 정책·수치·현재 상태는 옵시디언 볼트와 코드로 확인한 뒤에만 사실로 쓴다.
2. 검색 결과는 재료다. 결과를 인용할 때는 날짜·에이전트·세션 앞자리를 함께 적는다.
3. `recent` 주입이 현재 작업과 무관하면 무시한다. 다른 프로젝트 기록이 섞이면 `--project` 를 좁힌다.
4. 결과에 비밀값이 보이면 그 세션 파일을 지우라고 사용자에게 알린다(색인은 마스킹하지만 원문은 남는다).

## 어디에 무엇이 있나

- DB: `~/.timecapsule/index.db` (원천 파일별 바이트 오프셋을 기억해 증분 색인)
- 설정: `~/.timecapsule/config.json` — `extra_markdown_dirs`(마크다운 아카이브 추가), `exclude_project_dirs`
- 원천: `~/.claude/projects/*/*.jsonl`, `~/.codex/sessions/**/*.jsonl`
- claude-mem 에서 가져온 관찰은 `--agent claude-mem` 으로 구분된다

상세: `references/format.md`(색인 항목 규격) · `references/migrate-claude-mem.md`(이관 절차)
