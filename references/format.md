# 색인 항목 규격 (스키마 2)

`~/.timecapsule/index.db` 의 `entries` 한 행 = 세션 안의 한 발화 또는 한 도구 호출.

| 열 | 값 |
|:--|:--|
| agent | `claude` · `codex` · `cowork`(Claude 데스크톱 로컬 에이전트) · `claude-mem`(이관분) · `markdown`(아카이브) |
| project | 세션의 작업 디렉터리(cwd). Claude 는 첫 줄의 `cwd`, Codex 는 `session_meta.cwd`, Cowork 는 사용자가 고른 폴더(없으면 VM 경로) |
| session_id | Claude `sessionId` · Codex `session_meta.id` · 이관분 `cm:<id>` · 마크다운 `md:<상대경로>` |
| ts | ISO 8601. 줄에 없으면 파일 수정 시각 |
| role | `user` · `assistant` · `tool` · `summary`(대화 압축 요약·claude-mem 요약) · `observation` · `note` |
| text | 2,000자 상한(도구 240자). 비밀값을 먼저 가린 뒤 자른다 |
| path · line | 원천 파일과 **파일 전체 기준** 줄 번호 — 원문을 다시 열 때 쓴다 |

`sessions` 표: 세션별 `origin`(Claude `entrypoint` · Codex `originator` · `cowork`)과 Cowork 제목.
`files` 표: 파일별 `offset·size·mtime·lines`, `forgotten`(1 이면 다시 색인하지 않는다).

## 무엇을 넣고 무엇을 빼나

- 넣는다: 사람 프롬프트, 어시스턴트 답 텍스트, 도구 호출 이름(+Bash 첫 줄·파일 경로·Grep/Glob 패턴과 경로·스킬 이름), 대화 압축 요약(`summary`)
- 뺀다: 도구 결과 본문, `isMeta` 줄, 시스템 리마인더·훅 주입·슬래시 명령·`<local-command-caveat>`·`<bash-stdout>` 표식이 섞인 사용자 메시지, 사이드체인(서브에이전트) 메시지, Codex 의 developer 역할·환경 컨텍스트 메시지, Cowork `audit.jsonl`, `claude-mem-observer-sessions` 디렉터리

## 비밀값 가림

AWS 키 · `sk-`/`ghp_`/`github_pat_`/`glpat-`/`npm_`/`xox?-` 토큰 · Bearer · JWT · Google API 키 · 개인키 블록 · URL 안의 비밀번호(`scheme://user:••••@host`) · `password=`·`secret=`·`api_key=` · 이름에 token/secret/password/key/credential 이 든 대입 중 값이 16자 이상이고 숫자가 섞인 것.

## 증분 색인

크기·수정시각이 같으면 잠금 없이 건너뛴다. 바뀐 파일은 `BEGIN IMMEDIATE` 로 잠근 뒤 오프셋을 다시 읽어 이어서 넣는다 — 동시에 도는 색인(여러 세션의 Stop 훅)이 같은 줄을 두 번 넣지 않는다. 줄바꿈으로 끝나지 않은 마지막 줄은 다음 색인에서 다시 읽는다. 파일이 짧아졌으면 그 파일 항목을 지우고 처음부터 읽는다. `--quick` 은 최신 파일부터 4초 예산. `recent`·`search` 도 조회 전에 2초 예산으로 짧게 색인한다(`--no-index` 로 끔).

원본 파일이 사라져도(Claude Code 의 기록 자동 정리) 색인 항목은 남는다. 지우려면 `forget`.

## 프로젝트 매칭

`recent --project P`·`search --project P` 가 같은 프로젝트로 보는 세션:

1. 세션 cwd 가 P 이거나 P 의 하위
2. cwd 가 달라도 도구 기록에 P 경로(`~/…` 표기 포함)를 2번 이상 남긴 세션 — `recent` 에 「작업폴더 밖(이 경로 언급 N회)」로 표시
3. claude-mem 이관분 중 프로젝트 이름이 P 의 폴더 이름과 같은 것(검색만)

상위 폴더나 홈에서 연 세션은 넣지 않는다. 경로 경계를 지킨다 — `/app` 은 `/app2`·`/app-x` 에 걸리지 않는다. `recent` 는 자동 실행 세션(origin `codex_exec`·`codex_sdk_ts`·`sdk-cli`·`sdk-ts`·`sdk-py`)을 기본으로 빼고, 지금 세션(`CLAUDE_CODE_SESSION_ID` 또는 훅 입력의 `session_id`)도 뺀다.

## 토크나이저

SQLite FTS5 `trigram`. 3글자 이상의 부분 문자열 일치라 한국어 조사·활용을 따로 처리하지 않아도 된다. 3글자 미만 단어는 본문 `instr` 로 거른다(19만 행 기준 수십 ms). 지원하지 않는 SQLite 면 `unicode61` 로 내려가고 `meta.tokenizer` 에 기록된다.

## 스키마 이전과 재색인

v1 DB 를 처음 여는 프로세스가 잠금 안에서 v2 로 올린다(열 추가·표 추가·트리거 추가, 기존 행은 그대로). v1 에서 쌓인 행의 줄 번호·걸러내기·가림을 새 규칙으로 맞추려면 `timecapsule rebuild --yes` —
DB 를 `index.db.bak-<시각>` 으로 백업한 뒤 **원본이 남은 파일만** 지우고 다시 읽는다. 원본이 없는 기록은 지우지 않고 새 걸러내기·가림 규칙만 적용한다(줄 번호는 고칠 수 없다).

## 프롬프트 시점 주입 (0.3, UserPromptSubmit)
`hook prompt` 는 훅 JSON 의 `prompt`·`cwd`·`session_id` 를 읽는다. 검색어는 영문·식별자 2자 이상과 한국어 2자 이상(조사·접미를 긴 것부터 떼되 어간이 2글자 이상 남을 때만)에서 상투어(요청 동사·접속어·지시어)를 뺀 것, 긴 말부터 6개다.
검색은 특정적인 조합부터 — 모든 말 AND → 둘씩 짝(최대 10) → 한두 말이면 낱말 — 세션 3개가 모일 때까지. 범위는 전역(다른 작업 폴더·Codex 포함)이고 같은 프로젝트 세션을 앞에 둔다. user·assistant·summary 만 보고 자동 실행 세션·지금 세션은 뺀다. 기본 120일.
6자 미만, `/` 로 시작, 훅·시스템 표식이 든 프롬프트, 검색어가 안 남는 프롬프트, 결과 0 이면 아무것도 내지 않는다. 출력은 `hookSpecificOutput.additionalContext`(≤1,200자) 하나. 색인은 하지 않으며(Stop 훅이 턴마다 한다) 4초 알람 안에 끝낸다. 환경변수 `TIMECAPSULE_PROMPT_DAYS`(0=전체)·`_SESSIONS`·`_CHARS`·`_TIMEOUT`.

## touched · lessons (0.3)
- `touched <경로>`: `role='tool'` 항목에서 경로 문자열(절대·`~`·상대·파일명)을 찾되 경계를 지킨다(`x.py` 는 `x.pyc` 에 안 걸린다). 세션별로 첫·마지막 시각·언급 수·도구 줄 3개와 첫 요청·마지막 결론을 낸다. timecapsule 자기 명령은 뺀다.
- `lessons`: `role='user'` · 400자 미만 · `#` 로 시작하지 않음(서브에이전트 지시문 제외) · 자동 실행 세션 제외 · 신호어(앞으로·다시는·하지 마·했잖아·말라고·금지·그만·항상·반드시·잊지 마·기억해) 중 하나 포함. **검토용 목록**이다 — 규칙 파일·메모리에는 사람이 고른 것만 옮긴다.
