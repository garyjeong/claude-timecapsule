---
name: timecapsule
description: "Local, daemon-free session memory for Claude Code, Claude Desktop (Cowork) and Codex. Use when the user asks what was done before, when a past decision or command needs to be recalled (\"지난번에 어떻게 했지\", \"전에 이 오류 봤는데\", \"어느 세션에서\", \"did we already\"), when starting work on a project that has prior sessions, or when claude-mem style recall is needed. Indexes ~/.claude/projects, Cowork sessions and ~/.codex/sessions into SQLite FTS5 (trigram + 2-char fallback, Korean-safe) and exposes `timecapsule recent|search|session`. Never treats a past session as current policy — the Obsidian vault stays the source of truth."
---

# /timecapsule

세션 기록(Claude Code · Claude 데스크톱 Cowork · Codex)을 로컬 SQLite 에 색인해 두고 다시 꺼내 쓴다. 데몬도, 외부 추론 호출도 없다.

## 언제 쓰나

- 「지난번에 어떻게 했지」「전에 이 오류 봤는데」「어느 세션에서 바꿨지」 — `search`
- 프로젝트 작업을 시작할 때 최근 흐름 파악 — `recent` (SessionStart 훅이 자동 주입)
- 특정 세션의 전개를 다시 보고 싶을 때 — `session <id>`

## 명령

```
timecapsule recent [--project P] [--limit 5] [--days N] [--include-auto]
timecapsule search "질의" [--project P] [--agent claude|codex|cowork|claude-mem] [--role user|assistant|tool|summary] [--days N] [--sort recent|rank] [--src]
timecapsule session <id 앞 8자리> [--offset N --limit N] [--src]
timecapsule tools [--session ID | --days N] [--commands]   # 지난 세션에 무슨 도구·명령을 썼나 (주 에이전트만)
timecapsule touched <경로> [--days N] [--limit N]           # 이 파일·폴더를 다룬 세션 — 요청·결론·도구 줄 (절대·상대경로·파일명)
timecapsule lessons [--days 30] [--all]                     # 「앞으로 …」「하지 마」 같은 교정 발화 후보 — 검토용. 규칙 파일에는 고른 것만 옮긴다
timecapsule forget <id> [--yes]      # 비밀값이 든 세션을 색인에서 지운다 (--yes 없이는 시험 실행)
timecapsule index [--quick]          # 훅과 조회 명령이 알아서 돌린다
timecapsule stats · doctor
```

- 검색: 3글자 이상은 trigram 색인, 2글자 단어(배포·오류·훅)는 본문 부분 일치로 찾는다. 여러 단어는 AND. 세션당 결과 3개까지(`--per-session`).
- 지금 세션과 과거의 `timecapsule search` 명령 자체는 결과에서 빠진다(`--include-current` 로 포함).
- `recent` 의 프로젝트 범위: 작업 폴더가 P 이거나 P 의 하위인 세션 + 폴더가 달라도 도구 기록에 P 경로를 2번 이상 남긴 세션(「작업폴더 밖」으로 표시). 상위 폴더·홈에서 연 세션은 넣지 않는다. 스크립트가 띄운 자동 실행(`codex exec`·`claude -p`)은 기본으로 뺀다.

## 규칙

1. **출력 머리의 문구를 지키라.** 세션 기록은 「당시의 판단」이다. 정책·수치·현재 상태는 옵시디언 볼트와 코드로 확인한 뒤에만 사실로 쓴다.
2. 검색 결과는 재료다. 결과를 인용할 때는 날짜·에이전트·세션 앞자리를 함께 적는다.
3. `recent` 주입이 현재 작업과 무관하면 무시한다.
4. 결과에 비밀값이 보이면 사용자에게 알리고 `timecapsule forget <id>` 를 제안한다. 원본 세션 파일은 따로 지워야 한다(forget 이 경로를 알려 준다).

## 어디에 무엇이 있나

- DB: `~/.timecapsule/index.db` (원천 파일별 바이트 오프셋·줄 수를 기억해 증분 색인)
- 설정: `~/.timecapsule/config.json` — `extra_markdown_dirs`(마크다운 아카이브 추가), `exclude_project_dirs`
- 원천: `~/.claude/projects/*/*.jsonl`, Cowork `~/Library/Application Support/Claude/local-agent-mode-sessions/…/.claude/projects/*/*.jsonl`, `~/.codex/sessions/**/*.jsonl`
- claude-mem 에서 가져온 관찰은 `--agent claude-mem` 으로 구분된다
- Claude 데스크톱 채팅에서는 같은 기능이 MCP 도구(`timecapsule_search`·`_recent`·`_session`·`_stats`)로 보인다

상세: `references/format.md`(색인 항목 규격) · `references/migrate-claude-mem.md`(이관 절차)
