"""timecapsule 회귀 테스트 — 표준 라이브러리만. 실행: python3 -m unittest discover -s tests

실제 ~/.claude · ~/.codex · ~/.timecapsule 은 건드리지 않는다. HOME 과 원천 경로를 전부 임시 폴더로 돌린다.
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin", "timecapsule")
TS = "2026-09-{:02d}T0{}:00:00.000Z"


def ts(day, hour=1):
    return TS.format(day, hour)


def load_engine():
    """모듈 상수(HOME·원천 경로)가 import 시점의 환경을 읽으므로 테스트마다 새로 읽는다."""
    loader = importlib.machinery.SourceFileLoader("tc_under_test", BIN)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def cl_user(sid, cwd, text, t, **kw):
    return dict(type="user", sessionId=sid, cwd=cwd, timestamp=t, message={"role": "user", "content": text}, **kw)


def cl_asst(sid, cwd, text, t, **kw):
    return dict(type="assistant", sessionId=sid, cwd=cwd, timestamp=t,
                message={"role": "assistant", "content": [{"type": "text", "text": text}]}, **kw)


def cl_tool(sid, cwd, name, inp, t):
    return dict(type="assistant", sessionId=sid, cwd=cwd, timestamp=t,
                message={"role": "assistant", "content": [{"type": "tool_use", "name": name, "input": inp}]})


def write_jsonl(path, objs, mode="a", tail=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode, encoding="utf-8") as fh:
        for o in objs:
            fh.write(json.dumps(o, ensure_ascii=False) + "\n")
        fh.write(tail)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="tc-test-")
        self.home = os.path.join(self.tmp, "home")
        self.claude = os.path.join(self.home, ".claude", "projects")
        self.codex = os.path.join(self.home, ".codex", "sessions")
        self.cowork = os.path.join(self.home, "cowork")
        for d in (self.claude, self.codex, self.cowork):
            os.makedirs(d)
        self.env = {"HOME": self.home, "TIMECAPSULE_HOME": os.path.join(self.tmp, "tc"),
                    "TIMECAPSULE_CLAUDE_DIR": self.claude, "TIMECAPSULE_CODEX_DIR": self.codex,
                    "TIMECAPSULE_COWORK_DIR": self.cowork, "TIMECAPSULE_NO_AUTO_INDEX": "1"}
        self._saved = {k: os.environ.get(k) for k in list(self.env) + ["CLAUDE_CODE_SESSION_ID"]}
        os.environ.update(self.env)
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        self.tc = load_engine()
        self.ws = os.path.join(self.home, "ws")
        self.proj = os.path.join(self.ws, "proj")

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp)

    def cli(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.tc.main(list(argv))
        self.assertEqual(rc, 0, buf.getvalue())
        return buf.getvalue()

    def cjson(self, *argv):
        return json.loads(self.cli(*argv, "--json"))

    def claude_file(self, sid, cwd="x"):
        return os.path.join(self.claude, "-" + cwd.strip("/").replace("/", "-"), sid + ".jsonl")

    def db(self):
        return sqlite3.connect(self.tc.DB_PATH)


class IndexTest(Base):
    def test_line_numbers_absolute_across_incremental_passes(self):
        f = self.claude_file("s1")
        write_jsonl(f, [{"type": "file-history-snapshot"}, cl_user("s1", self.proj, "첫 요청입니다", ts(1)),
                        cl_asst("s1", self.proj, "첫 답입니다", ts(1))])
        self.cli("index")
        write_jsonl(f, [cl_user("s1", self.proj, "두번째 요청", ts(2)), {"type": "system"},
                        cl_asst("s1", self.proj, "두번째 답", ts(2))], tail='{"type": "user", "part')  # 쓰는 중인 줄
        self.cli("index")
        with open(f, encoding="utf-8") as fh:
            src = fh.read().split("\n")
        rows = self.db().execute("SELECT line, text FROM entries ORDER BY id").fetchall()
        self.assertEqual(len(rows), 4)
        for line, text in rows:
            self.assertIn(json.dumps(text, ensure_ascii=False)[1:-1], src[line - 1])
        # 마저 쓰이면 그 줄도 들어간다
        with open(f, "a", encoding="utf-8") as fh:
            fh.write('ial": 1}\n')
        write_jsonl(f, [cl_user("s1", self.proj, "세번째 요청", ts(3))])
        self.cli("index")
        line = self.db().execute("SELECT line FROM entries WHERE text='세번째 요청'").fetchone()[0]
        self.assertEqual(line, 8)

    def test_noise_filters_and_compact_summary(self):
        f = self.claude_file("s2")
        write_jsonl(f, [
            cl_user("s2", self.proj, "<local-command-caveat>Caveat: The messages below were generated", ts(1)),
            cl_user("s2", self.proj, "메타 줄", ts(1), isMeta=True),
            cl_user("s2", self.proj, "진짜 첫 요청", ts(1)),
            cl_user("s2", self.proj, "사이드체인", ts(1), isSidechain=True),
            cl_user("s2", self.proj, "This session is being continued from a previous conversation. 요약…", ts(2),
                    isCompactSummary=True),
            cl_asst("s2", self.proj, "결론", ts(2)),
        ])
        self.cli("index")
        roles = dict(self.db().execute("SELECT text, role FROM entries").fetchall())
        self.assertEqual(roles.get("진짜 첫 요청"), "user")
        self.assertEqual(sorted(roles.values()), ["assistant", "summary", "user"])
        r = self.cjson("recent", "--project", self.proj)
        self.assertEqual(r[0]["first_user"], "진짜 첫 요청")

    def test_hard_timeout_mid_file_loses_no_line(self):
        f = self.claude_file("to")
        write_jsonl(f, [cl_user("to", self.proj, f"줄 {i} 내용", ts(1)) for i in range(6)])
        real, tc = json, self.tc
        calls = {"n": 0}

        class Flaky:
            def __getattr__(self, name):
                return getattr(real, name)

            def loads(self, *a, **kw):
                calls["n"] += 1
                if calls["n"] == 3:  # 파서의 json.loads 한가운데서 시간 초과
                    raise tc.HardTimeout("budget")
                return real.loads(*a, **kw)
        tc.json = Flaky()
        try:
            self.cli("index")
        finally:
            tc.json = real
        self.cli("index")
        lines = [r[0] for r in self.db().execute("SELECT line FROM entries ORDER BY line")]
        self.assertEqual(lines, [1, 2, 3, 4, 5, 6])

    def test_index_is_private(self):
        os.makedirs(self.env["TIMECAPSULE_HOME"], mode=0o755)
        os.chmod(self.env["TIMECAPSULE_HOME"], 0o755)
        write_jsonl(self.claude_file("p1"), [cl_user("p1", self.proj, "비공개 확인", ts(1))])
        self.cli("index")
        mode = lambda p: os.stat(p).st_mode & 0o777
        self.assertEqual(mode(self.env["TIMECAPSULE_HOME"]), 0o700)
        for f in os.listdir(self.env["TIMECAPSULE_HOME"]):
            self.assertEqual(mode(os.path.join(self.env["TIMECAPSULE_HOME"], f)), 0o600, f)

    def test_concurrent_indexers_do_not_duplicate(self):
        f = self.claude_file("big")
        write_jsonl(f, [cl_user("big", self.proj, f"요청 {i:05d} 내용", ts(1)) for i in range(3000)])
        procs = [subprocess.Popen([sys.executable, BIN, "index", "--quiet"], env=dict(os.environ)) for _ in range(4)]
        for p in procs:
            self.assertEqual(p.wait(timeout=60), 0)
        n, d = self.db().execute("SELECT COUNT(*), COUNT(DISTINCT text) FROM entries").fetchone()
        self.assertEqual((n, d), (3000, 3000))

    def test_cowork_source_uses_selected_folder_and_title(self):
        local = os.path.join(self.cowork, "acct", "org", "local_abc")
        os.makedirs(os.path.dirname(local))
        with open(local + ".json", "w", encoding="utf-8") as fh:
            json.dump({"title": "문서 정리", "userSelectedFolders": [self.proj], "cwd": "/sessions/vm-x"}, fh)
        write_jsonl(os.path.join(local, ".claude", "projects", "-sessions-vm-x", "cw1.jsonl"),
                    [cl_user("cw1", "/sessions/vm-x", "코워크 요청", ts(4)), cl_asst("cw1", "/sessions/vm-x", "끝", ts(4))])
        write_jsonl(os.path.join(local, "audit.jsonl"), [{"type": "user", "session_id": "cw1"}])  # 색인 대상 아님
        self.cli("index")
        r = self.cjson("recent", "--project", self.proj)
        self.assertEqual([(x["agent"], x["title"], x["origin"]) for x in r], [("cowork", "문서 정리", "cowork")])


class RedactTest(Base):
    def test_secrets_masked_and_config_values_kept(self):
        secrets = {
            "postgres://app:S3cretPw9@db.example.com/x": "S3cretPw9",
            "key AIzaSyA1234567890abcdefghijklmnopqrstu": "AIzaSyA1234567890abcdefghijklmnopqrstu",
            "export GITHUB_TOKEN=ghp_abcdefghijklmnop1234567890": "ghp_abcdefghijklmnop1234567890",
            "SLACK_WEBHOOK_TOKEN: abcdefgh12345678ijkl": "abcdefgh12345678ijkl",
            "github_pat_11ABCDEFG0123456789_abcdefghijk": "github_pat_11ABCDEFG0123456789_abcdefghijk",
            "-----BEGIN OPENSSH " + "PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAA\n-----END OPENSSH " + "PRIVATE KEY-----":
                "b3BlbnNzaC1rZXktdjEAAAAA",  # 가짜 키 — 저장소 비밀값 검사에 걸리지 않게 이어 붙여 만든다
            "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY1": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY1",
            '{"password": "hunter2hunter2"}': "hunter2hunter2",
            'password="abc defghijk"': "defghijk",
            '{\\"password\\": \\"escapedpw99\\"}': "escapedpw99",
            "Authorization: Basic dXNlcjpwYXNzd29yZA==": "dXNlcjpwYXNzd29yZA==",
            'password="abcdef ghijkl"': "ghijkl",
            "client_secret: 'q8w7e6r5t4'": "q8w7e6r5t4",
            "curl -u admin:Sup3rPass https://x": "Sup3rPass",
            "DB_PASSWORD=$ecret123x": "$ecret123x",
            "password=$lowercase99": "lowercase99",
        }
        for text, raw in secrets.items():
            self.assertNotIn(raw, self.tc.redact(text), text)
        for keep in ("tokenizer=trigram", "max_tokens: 4096", "ssh://git@github.com/org/repo", "http://localhost:8080/api",
                     "token 사용량 12345", "password=${DB_PASSWORD}", '"password": "<your-password>"', "secret_name=prod/db",
                     "input_tokens: 123456", "password: str", "git push -u origin main", "token_count=1234567",
                     "SecretId: viewster/prod/db", "secretName=prod/db", "password=$DB_PASSWORD", "api_key=%API_KEY%"):
            self.assertEqual(self.tc.redact(keep), keep)

    def test_redact_is_idempotent(self):
        once = self.tc.redact('{"password": "hunter2hunter2", "api_key": "abcd1234efgh"}')
        self.assertEqual(self.tc.redact(once), once)
        self.assertEqual(once, '{"password": "••••", "api_key": "••••"}')

    def test_redaction_happens_before_clipping(self):
        text = "x" * 1990 + " password=hunter2hunter2hunter2"
        self.assertNotIn("hunter2", self.tc.clean(text, "user"))


class SearchTest(Base):
    def setUp(self):
        super().setUp()
        write_jsonl(self.claude_file("s1"), [
            cl_user("s1", self.proj, "스테이징 배포 오류 원인을 찾아줘", ts(1)),
            cl_asst("s1", self.proj, "훅 등록이 빠져 있었다", ts(1)),
            cl_tool("s1", self.proj, "Bash", {"command": "timecapsule search 배포"}, ts(1)),
        ])
        write_jsonl(self.claude_file("s2"), [cl_user("s2", self.proj, "DB 마이그레이션 순서", ts(2))])
        self.cli("index")

    def hits(self, q, *extra):
        return self.cjson("search", q, *extra)

    def test_two_char_korean_terms(self):
        self.assertEqual([h["session"] for h in self.hits("배포")], ["s1"])
        self.assertEqual(len(self.hits("훅")), 1)
        self.assertEqual(len(self.hits("배포 오류")), 1)
        self.assertEqual(len(self.hits("배포 마이그레이션")), 0)  # AND
        self.assertEqual(len(self.hits("db")), 1)  # 대소문자 무시
        self.assertIn("[배포]", self.hits("배포")[0]["snippet"])

    def test_own_search_commands_and_current_session_excluded(self):
        self.assertEqual({h["role"] for h in self.hits("search")}, set())  # 'timecapsule search …' 도구 행
        os.environ["CLAUDE_CODE_SESSION_ID"] = "s1"
        self.assertEqual(len(self.hits("배포")), 0)
        self.assertEqual(len(self.hits("배포", "--include-current")), 1)

    def test_per_session_cap_and_rank(self):
        write_jsonl(self.claude_file("s3"), [cl_asst("s3", self.proj, f"배포 기록 {i}", ts(3)) for i in range(10)])
        self.cli("index")
        hits = self.hits("배포 기록")
        self.assertEqual(sum(1 for h in hits if h["session"] == "s3"), 3)
        self.assertEqual(len(self.hits("배포 기록", "--per-session", "0")), 10)
        self.assertTrue(self.hits("마이그레이션", "--sort", "rank"))


class ProjectScopeTest(Base):
    def test_recent_scope(self):
        other = os.path.join(self.home, "other")
        sessions = {
            "A": (self.proj, []),                                     # 같은 폴더
            "B": (os.path.join(self.proj, "sub"), []),                 # 하위 폴더
            "C": (self.ws, []),                                        # 상위 폴더 — 뺀다
            "D": (self.home, []),                                      # 홈 — 뺀다
            "E": (other, [os.path.join(self.proj, "a.py"), "~/ws/proj/b.py"]),  # 밖에서 이 경로를 두 번 다룸
            "F": (other, [self.proj + "2/a.py", self.proj + "-x/b.py"]),        # 이름만 비슷한 형제 경로
            "G": (other, [os.path.join(self.proj, "c.py")]),                    # 한 번뿐 — 문턱 미달
        }
        for sid, (cwd, paths) in sessions.items():
            objs = [cl_user(sid, cwd, f"{sid} 요청", ts(5))]
            objs += [cl_tool(sid, cwd, "Read", {"file_path": p}, ts(5)) for p in paths]
            write_jsonl(self.claude_file(sid, cwd), objs)
        self.cli("index")
        got = {r["session"]: r["path_mentions"] for r in self.cjson("recent", "--project", self.proj, "--limit", "20")}
        self.assertEqual(got, {"A": 0, "B": 0, "E": 2})
        self.assertIn("작업폴더 밖(이 경로 언급 2회)", self.cli("recent", "--project", self.proj, "--limit", "20"))
        self.assertIn("C", {r["session"] for r in self.cjson("recent", "--project", self.ws, "--limit", "20")})
        # 새 프로젝트는 무관한 세션 대신 "없음"
        self.assertIn("세션 기록 없음", self.cli("recent", "--project", os.path.join(self.home, "brand-new")))

    def test_auto_origins_hidden_from_recent_but_searchable(self):
        write_jsonl(self.claude_file("human", self.proj), [cl_user("human", self.proj, "사람이 연 세션", ts(6), entrypoint="cli")])
        write_jsonl(self.claude_file("bot", self.proj), [cl_user("bot", self.proj, "스크립트가 연 세션", ts(7), entrypoint="sdk-cli")])
        write_jsonl(os.path.join(self.codex, "2026", "09", "07", "rollout-x.jsonl"), [
            {"type": "session_meta", "payload": {"id": "cx1", "cwd": self.proj, "originator": "codex_exec"}},
            {"type": "response_item", "timestamp": ts(8), "payload": {"type": "message", "role": "user",
                                                                     "content": [{"type": "input_text", "text": "코덱스 위임 작업"}]}},
        ])
        self.cli("index")
        self.assertEqual([r["session"] for r in self.cjson("recent", "--project", self.proj)], ["human"])
        self.assertEqual({r["session"] for r in self.cjson("recent", "--project", self.proj, "--include-auto")},
                         {"human", "bot", "cx1"})
        self.assertEqual(len(self.cjson("search", "코덱스 위임")), 1)

    def test_current_session_excluded_from_recent(self):
        write_jsonl(self.claude_file("now", self.proj), [cl_user("now", self.proj, "지금 세션", ts(9))])
        write_jsonl(self.claude_file("old", self.proj), [cl_user("old", self.proj, "지난 세션", ts(8))])
        self.cli("index")
        os.environ["CLAUDE_CODE_SESSION_ID"] = "now"
        self.assertEqual([r["session"] for r in self.cjson("recent", "--project", self.proj)], ["old"])
        self.assertEqual(len(self.cjson("recent", "--project", self.proj, "--include-current")), 2)


class ManageTest(Base):
    def test_forget_removes_and_stays_forgotten(self):
        f = self.claude_file("sec", self.proj)
        write_jsonl(f, [cl_user("sec", self.proj, "비밀 이야기 hunter2", ts(1))])
        write_jsonl(self.claude_file("keep", self.proj), [cl_user("keep", self.proj, "남길 이야기", ts(1))])
        self.cli("index")
        self.assertIn("시험 실행", self.cli("forget", "sec"))
        self.assertEqual(len(self.cjson("search", "hunter2")), 1)
        out = self.cli("forget", "sec", "--yes")
        self.assertIn(f, out)  # 남은 원본 경로를 알려 준다
        self.assertEqual(len(self.cjson("search", "hunter2")), 0)
        write_jsonl(f, [cl_user("sec", self.proj, "이어서 hunter2", ts(2))])
        self.cli("index")
        self.assertEqual(len(self.cjson("search", "hunter2")), 0)
        self.assertEqual(len(self.cjson("search", "남길 이야기")), 1)
        con = self.db()
        con.execute("INSERT INTO fts(fts) VALUES('integrity-check')")

    def test_session_prefix_ambiguity_and_paging(self):
        write_jsonl(self.claude_file("abc1"), [cl_user("abc1", self.proj, f"줄 {i}", ts(1)) for i in range(5)])
        write_jsonl(self.claude_file("abc2"), [cl_user("abc2", self.proj, "다른 세션", ts(1))])
        self.cli("index")
        self.assertIn("더 길게", self.cli("session", "abc"))
        out = self.cli("session", "abc1", "--offset", "1", "--limit", "2")
        self.assertIn("줄 1", out)
        self.assertNotIn("줄 3", out)
        self.assertIn("--offset 3", out)

    def test_v1_database_migrates_and_rebuild_fixes_rows(self):
        os.makedirs(self.env["TIMECAPSULE_HOME"])
        live = self.claude_file("live", self.proj)
        write_jsonl(live, [{"type": "file-history-snapshot"}, cl_user("live", self.proj, "살아 있는 요청", ts(1)),
                           cl_asst("live", self.proj, "답", ts(1))])
        gone = os.path.join(self.tmp, "deleted.jsonl")
        con = sqlite3.connect(self.tc.DB_PATH)
        con.executescript("""
            CREATE TABLE files(path TEXT PRIMARY KEY, offset INTEGER NOT NULL DEFAULT 0, size INTEGER NOT NULL DEFAULT 0,
              mtime REAL NOT NULL DEFAULT 0, agent TEXT, session_id TEXT, project TEXT, indexed_at REAL);
            CREATE TABLE entries(id INTEGER PRIMARY KEY, agent TEXT NOT NULL, project TEXT, session_id TEXT NOT NULL,
              ts TEXT NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL, path TEXT, line INTEGER);
            CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
            CREATE VIRTUAL TABLE fts USING fts5(text, content='entries', content_rowid='id', tokenize='trigram');
            CREATE TRIGGER entries_ai AFTER INSERT ON entries BEGIN INSERT INTO fts(rowid, text) VALUES (new.id, new.text); END;
            CREATE TRIGGER entries_ad AFTER DELETE ON entries BEGIN INSERT INTO fts(fts, rowid, text) VALUES('delete', old.id, old.text); END;
            INSERT INTO meta VALUES('tokenizer','trigram'), ('schema','1');
        """)
        rows = [("claude", self.proj, "live", ts(1), "user", "살아 있는 요청", live, 1),   # 줄 번호가 틀린 v1 행
                ("claude", self.proj, "old", ts(1), "user", "<local-command-caveat>Caveat: x", gone, 1),
                ("claude", self.proj, "old", ts(1), "user", "This session is being continued from a previous conversation …", gone, 2),
                ("claude", self.proj, "old", ts(1), "assistant", "접속 postgres://u:Pw12345678@db.prod.io/x", gone, 3),
                ("claude", self.proj, "old", ts(1), "user", "지워진 파일의 기록", gone, 4)]
        con.executemany("INSERT INTO entries(agent, project, session_id, ts, role, text, path, line) VALUES(?,?,?,?,?,?,?,?)", rows)
        con.execute("INSERT INTO files VALUES(?,?,?,?,?,?,?,?)", (live, os.path.getsize(live), os.path.getsize(live),
                                                                   os.path.getmtime(live), "claude", "live", self.proj, 0))
        con.commit()
        con.close()
        self.assertIn("시험 실행", self.cli("rebuild"))
        self.cli("rebuild", "--yes")
        con = self.db()
        self.assertEqual(con.execute("SELECT v FROM meta WHERE k='schema'").fetchone()[0], "2")
        self.assertEqual(con.execute("SELECT line FROM entries WHERE text='살아 있는 요청'").fetchall(), [(2,)])
        old = dict(con.execute("SELECT text, role FROM entries WHERE session_id='old'").fetchall())
        self.assertEqual(sorted(old.values()), ["assistant", "summary", "user"])  # caveat 행은 지워짐
        self.assertIn("지워진 파일의 기록", old)
        self.assertEqual(len(self.cjson("search", "Pw12345678")), 0)  # FTS 에서도 사라짐
        self.assertEqual(len(self.cjson("search", "db.prod.io")), 1)
        con.execute("INSERT INTO fts(fts) VALUES('integrity-check')")
        con.commit()  # 테스트 연결이 쓰기 잠금을 쥔 채로 남지 않게
        self.assertEqual(len([f for f in os.listdir(self.env["TIMECAPSULE_HOME"]) if ".bak-" in f]), 1)
        # v1 행에서 이어 색인하면 줄 수를 세어 이어 붙인다
        write_jsonl(live, [cl_user("live", self.proj, "이어진 요청", ts(2))])
        self.cli("index")
        self.assertEqual(con.execute("SELECT line FROM entries WHERE text='이어진 요청'").fetchone()[0], 4)


    def test_v1_offset_resume_counts_lines(self):
        os.makedirs(self.env["TIMECAPSULE_HOME"])
        f = self.claude_file("res", self.proj)
        write_jsonl(f, [cl_user("res", self.proj, "앞 요청 하나", ts(1)), cl_asst("res", self.proj, "앞 답 하나", ts(1))])
        size = os.path.getsize(f)
        con = sqlite3.connect(self.tc.DB_PATH)
        con.executescript("""
            CREATE TABLE files(path TEXT PRIMARY KEY, offset INTEGER NOT NULL DEFAULT 0, size INTEGER NOT NULL DEFAULT 0,
              mtime REAL NOT NULL DEFAULT 0, agent TEXT, session_id TEXT, project TEXT, indexed_at REAL);
            CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
            INSERT INTO meta VALUES('schema','1');
        """)
        con.execute("INSERT INTO files VALUES(?,?,?,?,?,?,?,?)", (f, size, size, 0, "claude", "res", self.proj, 0))
        con.commit()
        con.close()
        write_jsonl(f, [cl_user("res", self.proj, "뒤 요청 셋째 줄", ts(2))])
        self.cli("index")
        self.assertEqual(self.db().execute("SELECT line FROM entries").fetchall(), [(3,)])


def codex_meta(sid, cwd, source="cli", originator="codex-tui"):
    return {"type": "session_meta", "payload": {"id": sid, "cwd": cwd, "source": source, "originator": originator}}


def codex_user(*frags, t=ts(1)):
    return {"type": "response_item", "timestamp": t, "payload": {
        "type": "message", "role": "user", "content": [{"type": "input_text", "text": f} for f in frags]}}


class CodexTest(Base):
    def codex_file(self, name, objs):
        path = os.path.join(self.codex, "2026", "09", "10", name + ".jsonl")
        write_jsonl(path, objs)
        return path

    def test_user_fragments_filtered(self):
        self.codex_file("r1", [
            codex_meta("cx1", self.proj),
            codex_user("# AGENTS.md instructions …", "<environment_context>cwd</environment_context>",
                       "<recommended_plugins>- a\n- b</recommended_plugins>",
                       '<in-app-browser-context source="ambient-ui-state">url: http://x</in-app-browser-context>\n배포 순서 알려줘',
                       '<image name=[Image #1] path="/tmp/a.png">', "</image>"),
            codex_user("The following is the Codex agent history whose request action you are assessing …", "추가 조각"),
        ])
        self.cli("index")
        rows = self.db().execute("SELECT role, text FROM entries WHERE agent='codex'").fetchall()
        self.assertEqual(rows, [("user", "배포 순서 알려줘")])

    def test_subagent_and_exec_hidden_from_recent(self):
        self.codex_file("r2", [codex_meta("tui", self.proj), codex_user("사람 요청")])
        self.codex_file("r3", [codex_meta("sub", self.proj, source={"subagent": {"parent": "tui"}}), codex_user("서브 요청")])
        self.codex_file("r4", [codex_meta("ex", self.proj, source="exec", originator="codex_exec"), codex_user("exec 요청")])
        self.cli("index")
        self.assertEqual([r["session"] for r in self.cjson("recent", "--project", self.proj)], ["tui"])
        origins = dict(self.db().execute("SELECT session_id, origin FROM sessions").fetchall())
        self.assertEqual(origins, {"tui": "codex-tui", "sub": "codex_subagent", "ex": "codex_exec"})

    def test_nearest_codex_process_decides(self):
        f = self.tc.nearest_codex_is_exec
        self.assertTrue(f(["bash hook.sh", "/opt/homebrew/bin/codex exec --json 'x'"]))
        self.assertTrue(f(["node /x/bin/codex.js -c model=gpt -m o4 exec"]))
        self.assertTrue(f(["/x/codex-aarch64-apple-darwin --profile p e 'hi'"]))
        self.assertFalse(f(["bash hook.sh", "/opt/homebrew/bin/codex -c model=x", "zsh -c 'codex exec later'"]))
        self.assertFalse(f(["zsh -c 'x; /opt/homebrew/bin/codex exec y'", "/opt/homebrew/bin/codex -m o4"]))  # 셸 문자열은 무시
        self.assertFalse(f(["/opt/homebrew/bin/codex resume abc"]))
        self.assertFalse(f(["zsh", "login"]))

    def test_codex_hooks_skip_auto_sessions(self):
        tui = self.codex_file("r5", [codex_meta("tui", self.proj), codex_user("지금 코덱스 세션")])
        ex = self.codex_file("r6", [codex_meta("ex", self.proj, source="exec", originator="codex_exec"), codex_user("exec")])
        write_jsonl(self.claude_file("prev", self.proj), [cl_user("prev", self.proj, "지난 클로드 세션", ts(8))])
        env = dict(os.environ)
        env.pop("TIMECAPSULE_NO_AUTO_INDEX", None)

        def hook(event, payload):
            return subprocess.run([sys.executable, BIN, "hook", event], input=json.dumps(payload), capture_output=True,
                                  text=True, env=env, timeout=60)
        r = hook("codex-session-start", {"cwd": self.proj, "transcript_path": ex})
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        r = hook("codex-session-start", {"cwd": self.proj, "transcript_path": tui})
        self.assertIn("지난 클로드 세션", r.stdout)
        self.assertNotIn("지금 코덱스 세션", r.stdout)  # 자기 세션은 빠진다
        r = hook("codex-stop", {"cwd": self.proj, "transcript_path": tui})
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        # 기록 파일이 아직 없으면 조상 프로세스로 판정 — 여기(unittest)는 codex exec 아래가 아니다
        r = hook("codex-session-start", {"cwd": self.proj, "transcript_path": os.path.join(self.tmp, "none.jsonl")})
        self.assertIn("지난 클로드 세션", r.stdout)
        # codex-prompt: exec 세션은 침묵, 대화형 세션은 프롬프트와 닿는 과거 세션을 Claude Code 와 같은 JSON 으로 낸다
        env["TIMECAPSULE_PROMPT_DAYS"] = "0"
        r = hook("codex-prompt", {"cwd": self.proj, "transcript_path": ex, "prompt": "지난 클로드 세션 이야기 다시"})
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        r = hook("codex-prompt", {"cwd": self.proj, "transcript_path": tui, "prompt": "지난 클로드 세션 이야기 다시"})
        out = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "UserPromptSubmit")
        self.assertIn("· prev ·", out["additionalContext"])
        self.assertNotIn("· tui ·", out["additionalContext"])


class HookAndMcpTest(Base):
    def setUp(self):
        super().setUp()
        write_jsonl(self.claude_file("cur", self.proj), [cl_user("cur", self.proj, "지금 세션 요청", ts(9))])
        write_jsonl(self.claude_file("prev", self.proj), [cl_user("prev", self.proj, "지난 세션 배포 요청", ts(8)),
                                                          cl_asst("prev", self.proj, "배포 완료", ts(8))])

    def run_bin(self, args, stdin=""):
        env = dict(os.environ)
        env.pop("TIMECAPSULE_NO_AUTO_INDEX", None)
        return subprocess.run([sys.executable, BIN] + args, input=stdin, capture_output=True, text=True, env=env, timeout=60)

    def test_session_start_hook_reads_stdin_and_excludes_current(self):
        r = self.run_bin(["hook", "session-start"], json.dumps({"session_id": "cur", "cwd": self.proj, "source": "resume"}))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("prev", r.stdout)
        self.assertNotIn("지금 세션 요청", r.stdout)
        r = self.run_bin(["hook", "session-start"], "")  # 입력이 없어도 죽지 않는다
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_hook_wrapper_fails_open_without_engine_on_path(self):
        env = dict(os.environ, PATH="/usr/bin:/bin", TIMECAPSULE_BIN="/nonexistent")
        r = subprocess.run(["bash", os.path.join(ROOT, "hooks", "session-start.sh")], input="{}", capture_output=True,
                           text=True, env=env, timeout=60)
        self.assertEqual(r.returncode, 0)

    def test_mcp_roundtrip(self):
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                                                          "clientInfo": {"name": "t", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "timecapsule_search", "arguments": {"query": "배포"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "timecapsule_recent", "arguments": {"project": "proj"}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "timecapsule_session", "arguments": {"id": "prev"}}},
            {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "nope", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 7, "method": "bogus"},
        ]
        r = self.run_bin(["mcp"], "".join(json.dumps(m) + "\n" for m in msgs))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = {m["id"]: m for m in map(json.loads, r.stdout.splitlines())}
        self.assertEqual(sorted(out), [1, 2, 3, 4, 5, 6, 7])  # 알림에는 답하지 않는다
        self.assertEqual(out[1]["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual({t["name"] for t in out[2]["result"]["tools"]},
                         {"timecapsule_search", "timecapsule_recent", "timecapsule_session", "timecapsule_stats",
                          "timecapsule_touched", "timecapsule_lessons"})
        self.assertIn("배포", out[3]["result"]["content"][0]["text"])
        self.assertIn("지난 세션 배포 요청", out[4]["result"]["content"][0]["text"])  # 폴더 이름 → 경로
        self.assertIn("배포 완료", out[5]["result"]["content"][0]["text"])
        self.assertTrue(out[6]["result"]["isError"])
        self.assertEqual(out[7]["error"]["code"], -32601)

class PromptHookTest(Base):
    """0.3 — UserPromptSubmit 주입: 프롬프트의 말로 과거 세션을 찾는다."""

    def hook(self, event, payload):
        return subprocess.run([sys.executable, BIN, "hook", event], input=json.dumps(payload), capture_output=True,
                              text=True, env=dict(os.environ, TIMECAPSULE_PROMPT_DAYS="0"), timeout=60)

    def test_prompt_terms_strip_particles_and_stopwords(self):
        t = self.tc.prompt_terms("정산 내역 버튼을 모바일 웹에도 넣어줘")
        for w in ("정산", "내역", "버튼", "모바일"):
            self.assertIn(w, t)
        for w in ("버튼을", "넣어줘", "웹에도"):
            self.assertNotIn(w, t)
        self.assertEqual(self.tc.prompt_terms("agency-agents, graft 조사해줘"), ["agency-agents", "graft"])
        self.assertIn("QR", self.tc.prompt_terms("후원 QR 카드 기본 꺼짐으로"))  # 2글자 영문 식별자
        self.assertEqual(self.tc.prompt_terms("요약해줘"), [])
        self.assertEqual(self.tc.prompt_terms("그리고 다시 확인해줘"), [])
        self.assertEqual(self.tc.prompt_terms("커밋하고 푸시해줘"), ["커밋"])
        self.assertLessEqual(len(self.tc.prompt_terms(" ".join(f"단어{i}" for i in range(20)))), 6)

    def test_prompt_hook_injects_related_sessions_only(self):
        other = os.path.join(self.ws, "other")
        write_jsonl(self.claude_file("old1", self.proj), [cl_user("old1", self.proj, "정산 내역 버튼을 모바일 웹에 추가해줘", ts(1)),
                                                        cl_asst("old1", self.proj, "모바일 웹 지갑에 정산 내역 버튼을 넣었다", ts(1))])
        write_jsonl(self.claude_file("old2", other), [cl_user("old2", other, "agency-agents 와 graft 를 아는가", ts(2)),
                                                    cl_asst("old2", other, "둘 다 안다", ts(2))])
        write_jsonl(self.claude_file("noise", self.proj), [cl_user("noise", self.proj, "날씨 이야기", ts(3))])
        write_jsonl(self.claude_file("cur", self.proj), [cl_user("cur", self.proj, "정산 내역 모바일 지금 세션", ts(4))])
        self.cli("index")
        r = self.hook("prompt", {"session_id": "cur", "cwd": self.proj, "prompt": "정산 내역 버튼을 모바일 웹에도 넣어줘"})
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "UserPromptSubmit")
        ctx = out["additionalContext"]
        self.assertIn("· old1 ·", ctx)
        self.assertIn("요청: 정산 내역 버튼을", ctx)
        self.assertNotIn("· cur ·", ctx)  # 지금 세션은 뺀다
        self.assertNotIn("noise", ctx)
        # 다른 작업 폴더의 세션도 찾는다 (전역 범위)
        r = self.hook("prompt", {"session_id": "cur", "cwd": self.proj, "prompt": "agency-agents, graft 조사해줘"})
        self.assertIn("· old2 ·", json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"])
        # 짧은 말·슬래시 명령·상투어뿐·무관한 말이면 아무것도 내지 않는다
        for p in ("응", "/clear", "요약해줘", "양자역학 강의 들려줘", "커밋하고 푸시해줘", "배포해줘"):  # 흔한 말 하나뿐이면 찾지 않는다
            r = self.hook("prompt", {"session_id": "cur", "cwd": self.proj, "prompt": p})
            self.assertEqual((r.returncode, r.stdout.strip()), (0, ""), p)
        r = self.hook("prompt", {})  # 입력이 없어도 죽지 않는다
        self.assertEqual((r.returncode, r.stdout.strip()), (0, ""))

    def test_prompt_hook_prefers_same_project_and_respects_budget(self):
        other = os.path.join(self.ws, "other")
        for i, (sid, cwd) in enumerate((("far", other), ("near", self.proj))):
            write_jsonl(self.claude_file(sid, cwd), [cl_user(sid, cwd, "오버레이 위젯 배율 문제", ts(1 + i)), cl_asst(sid, cwd, "배율은 폭이 아니다", ts(1 + i))])
        self.cli("index")
        r = subprocess.run([sys.executable, BIN, "hook", "prompt"], input=json.dumps({"cwd": self.proj, "prompt": "오버레이 위젯 배율 문제 다시 보자"}),
                           capture_output=True, text=True, env=dict(os.environ, TIMECAPSULE_PROMPT_DAYS="0", TIMECAPSULE_PROMPT_SESSIONS="1"), timeout=60)
        ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("· near ·", ctx)
        self.assertNotIn("· far ·", ctx)


class TouchedLessonsTest(Base):
    def test_touched_groups_tool_hits_by_session(self):
        f1 = os.path.join(self.proj, "app", "x.py")
        write_jsonl(self.claude_file("t1", self.proj), [cl_user("t1", self.proj, "x 를 고쳐줘", ts(1)),
                                                      cl_tool("t1", self.proj, "Edit", {"file_path": f1}, ts(1)),
                                                      cl_tool("t1", self.proj, "Read", {"file_path": f1}, ts(1)),
                                                      cl_asst("t1", self.proj, "고쳤다", ts(1))])
        write_jsonl(self.claude_file("t2", self.proj), [cl_user("t2", self.proj, "x2 를 봐줘", ts(2)),
                                                      cl_tool("t2", self.proj, "Read", {"file_path": f1 + "c"}, ts(2))])  # x.pyc — 경계 밖
        write_jsonl(self.claude_file("t3", self.proj), [cl_user("t3", self.proj, "검색만", ts(3)),
                                                      cl_tool("t3", self.proj, "Bash", {"command": "timecapsule touched app/x.py"}, ts(3))])
        self.cli("index")
        rows = self.cjson("touched", "app/x.py")
        self.assertEqual([r["session"] for r in rows], ["t1"])
        self.assertEqual((rows[0]["hits"], rows[0]["first_user"], rows[0]["last_assistant"]), (2, "x 를 고쳐줘", "고쳤다"))
        self.assertEqual([r["session"] for r in self.cjson("touched", f1)], ["t1"])  # 절대경로도
        self.assertEqual(self.cjson("touched", "app/x.py", "--days", "1"), [])
        self.assertIn("'app/x.py' 를 다룬 세션 1개", self.cli("touched", "app/x.py"))

    def test_lessons_lists_short_interactive_corrections_only(self):
        write_jsonl(self.claude_file("l1", self.proj), [cl_user("l1", self.proj, "앞으로 테스트는 AI-Tester 계정으로만 해", ts(1))])
        write_jsonl(self.claude_file("l2", self.proj), [cl_user("l2", self.proj, "# 과제\n이 저장소를 읽어라. 파일을 고치지 마라", ts(2))])  # 서브에이전트 지시문
        write_jsonl(self.claude_file("l3", self.proj), [cl_user("l3", self.proj, "하지 마 " + "가" * 500, ts(3))])  # 너무 길다
        write_jsonl(self.claude_file("l4", self.proj), [cl_user("l4", self.proj, "오늘 날씨 좋다", ts(4))])
        write_jsonl(self.claude_file("l5", os.path.join(self.ws, "other")), [cl_user("l5", os.path.join(self.ws, "other"), "다시는 그러지 마", ts(5))])
        self.cli("index")
        rows = self.cjson("lessons", "--project", self.proj, "--days", "0")
        self.assertEqual([(r["session"], r["pattern"]) for r in rows], [("l1", "앞으로")])
        self.assertEqual([r["session"] for r in self.cjson("lessons", "--all", "--days", "0")], ["l5", "l1"])
        out = self.cli("lessons", "--project", self.proj, "--days", "0")
        self.assertIn("검토용 목록", out)



if __name__ == "__main__":
    unittest.main()
