# 색인 항목 규격

`~/.timecapsule/index.db` 의 `entries` 한 행 = 세션 안의 한 발화 또는 한 도구 호출.

| 열 | 값 |
|:--|:--|
| agent | `claude` · `codex` · `claude-mem`(이관분) · `markdown`(아카이브) |
| project | 세션의 작업 디렉터리(cwd). Claude 는 첫 줄의 `cwd`, Codex 는 `session_meta.cwd` |
| session_id | Claude `sessionId` · Codex `session_meta.id` · 이관분 `cm:<id>` · 마크다운 `md:<상대경로>` |
| ts | ISO 8601. 줄에 없으면 파일 수정 시각 |
| role | `user` · `assistant` · `tool` · `observation` · `summary` · `note` |
| text | 2,000자 상한. 비밀값 패턴은 마스킹(AWS 키·토큰·Bearer·JWT·password=) |
| path · line | 원천 파일과 줄 번호 — 원문을 다시 열 때 쓴다 |

## 무엇을 넣고 무엇을 빼나

- 넣는다: 사람 프롬프트, 어시스턴트 답 텍스트, 도구 호출 이름(+Bash 첫 줄·파일 경로·스킬 이름)
- 뺀다: 도구 결과 본문, 시스템 리마인더·훅 주입·슬래시 명령 표식이 섞인 사용자 메시지, 사이드체인(서브에이전트) 메시지, Codex 의 developer 역할·환경 컨텍스트 메시지, `claude-mem-observer-sessions` 디렉터리

## 증분 색인

`files` 표가 파일별 `offset·size·mtime` 을 기억한다. 크기·수정시각이 같으면 건너뛰고, 줄바꿈으로 끝나지 않은 마지막 줄은 다음 색인에서 다시 읽는다. 파일이 짧아졌으면 그 파일 항목을 지우고 처음부터 읽는다. `--quick` 은 최신 파일부터 4초 예산.

## 프로젝트 매칭

`recent --project P` 는 세션 cwd 가 P 와 같거나, P 의 하위이거나, P 가 그 cwd 의 하위일 때 잡는다. 워크스페이스 루트에서 부르면 하위 저장소 세션이, 하위 저장소에서 부르면 루트 세션도 함께 보인다.

## 토크나이저

SQLite FTS5 `trigram`. 3글자 이상의 부분 문자열 일치라 한국어 조사·활용을 따로 처리하지 않아도 된다. 지원하지 않는 SQLite 면 `unicode61` 로 내려가고 `meta.tokenizer` 에 기록된다.
