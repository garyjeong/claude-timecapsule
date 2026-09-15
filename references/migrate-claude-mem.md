# claude-mem 에서 옮겨오기

claude-mem 은 LLM 관찰자가 세션을 요약한 「관찰」과 「세션 요약」을 SQLite(`~/.claude-mem/claude-mem.db`)에 쌓는다. timecapsule 은 원문 세션을 직접 색인하므로 관찰이 없어도 되지만, 과거 관찰은 검색 가치가 있으니 한 번 가져온다.

```
timecapsule migrate-claude-mem            # observations + session_summaries → agent='claude-mem'
timecapsule search "질의" --agent claude-mem
```

- 읽기 전용으로 연다. 원본은 건드리지 않는다.
- 다시 돌리면 「이미 이관됨」으로 멈춘다. 덮어쓰려면 `--force`.
- Chroma 벡터 데이터는 가져오지 않는다(원문이 색인되므로 불필요).

## 플러그인 걷어내기 (선택)

1. `claude plugin uninstall claude-mem@thedotmack` — 훅·MCP·세션 시작 주입이 함께 사라진다.
2. 워커가 떠 있으면 `pkill -f worker-service.cjs`.
3. `~/.claude-mem/` 은 이관 결과를 확인한 뒤 지운다(1.5 GB 안팎).

훅을 걷어내지 않으면 timecapsule 을 써도 옛 장애 경로(워커 미실행·타임아웃·관찰자 할당량)가 그대로 남는다.
