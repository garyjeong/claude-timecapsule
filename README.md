# claude-timecapsule

Claude Code · Claude 데스크톱 용 로컬 세션 메모리. 데몬·외부 추론 없이 세션 기록을 SQLite FTS5 에 색인하고, 세션 시작 때 최근 맥락을 넣어 주며, 언제든 `timecapsule search` 로 되찾는다. claude-mem 의 대체물이다.

- 원천: `~/.claude/projects/*/*.jsonl`(Claude Code — CLI·데스크톱 Code 탭) + Cowork 세션 + `~/.codex/sessions/**/*.jsonl`
- 저장: `~/.timecapsule/index.db` — 증분 색인, 파일별 오프셋·줄 수 기억, 동시 색인에도 중복 없음
- 검색: trigram 토크나이저 + 2글자 단어는 부분 일치 (한국어)
- 주입: SessionStart 훅이 이 프로젝트를 다룬 최근 세션 5개 요약(≤3k자)을 넣는다 — 상위 폴더·홈 세션, 자동 실행 세션, 지금 세션은 뺀다
- 프롬프트 시점 주입(0.3): UserPromptSubmit 훅이 그 프롬프트의 말(조사를 떼고, 상투어를 빼고)로 전체 기록을 찾아 닿는 세션 3개(≤1.2k자)를 넣는다 — 다른 작업 폴더·Codex 세션도 보이고, 짧은 말·슬래시 명령·무관한 말이면 아무것도 넣지 않는다. 색인은 하지 않고 4초 안에 끝낸다
- `touched <경로>`: 이 파일·폴더를 다룬 세션(요청·결론·도구 줄). `lessons`: 「앞으로 …」「하지 마」 같은 교정 발화 후보 — 검토용 목록이며 규칙 파일에 자동으로 쓰지 않는다
- 데스크톱 채팅: MCP 서버(`timecapsule mcp`)로 검색·최근·세션 도구를 제공한다
- 실패 처리: CLI 는 실패 시 exit 1(stderr 한 줄), 훅은 자체 fail-open — 세션을 막지 않는다. 예산 초과 시 부분 결과 유지
- 비밀값: 키·토큰·JWT·개인키·URL 비밀번호 등은 색인 시 마스킹. 지울 때는 `timecapsule forget <id>`

## 설치

```
./install.sh        # 심링크 + Claude Code 훅 + 데스크톱 MCP 등록 + 증분 색인 (여러 번 돌려도 된다)
./uninstall.sh      # 되돌리기 (--purge 면 색인도 삭제)
timecapsule rebuild --yes        # 0.1 에서 올릴 때 한 번 — 백업 후 원본이 남은 파일을 다시 색인
timecapsule migrate-claude-mem   # 옛 claude-mem 관찰 가져오기 (선택)
# 0.2 → 0.3: ./install.sh 를 다시 돌리면 UserPromptSubmit 훅이 추가된다. 스키마는 그대로라 rebuild 는 필요 없다
```

- 훅 명령 문자열은 판이 바뀌어도 같다 — 이미 열린 Claude Code 세션도 다음 턴부터 새 엔진을 쓴다.
- 데스크톱 MCP 는 앱을 완전히 종료했다가 다시 켜야 잡힌다.

Codex 쪽 짝은 [codex-timecapsule](../codex-timecapsule) — 같은 엔진, 같은 DB 를 쓴다(엔진 사본은 `sync-engine.sh` 로 맞춘다).

## 구성

```
SKILL.md            Claude Code 스킬 (~/.claude/skills/timecapsule 로 심링크)
bin/timecapsule     엔진 (python3.9+ 표준 라이브러리, 파일 하나) — CLI · 훅 진입점 · MCP 서버
hooks/session-start.sh · hooks/prompt.sh · hooks/stop.sh
references/format.md · references/migrate-claude-mem.md
tests/              python3 -m unittest discover -s tests
```
