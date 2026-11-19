"""Server tests: run with `python3 -m unittest discover -s tests` from the ByEar folder.

Each test class starts a real server.py on a free port with a temporary project, temporary data folder
and tests/fake_agent.py instead of Claude Code. Requires ffmpeg / ffprobe.
"""
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def tone(path, freq, vol=0.5, sec=2.0):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency={freq}:duration={sec}:sample_rate=48000", "-af", f"volume={vol}",
                    "-ac", "1", "-c:a", "pcm_s16le", path], check=True)


class Server:
    """Temporary project + server process."""

    def __init__(self, fake_mode="edit", settings=None):
        self.tmp = tempfile.mkdtemp(prefix="byear_test_")
        game = os.path.join(self.tmp, "game")
        a = os.path.join(game, "grp", "01_a")
        b = os.path.join(game, "grp", "02_b")
        os.makedirs(a)
        os.makedirs(b)
        tone(os.path.join(a, "en.wav"), 220)
        tone(os.path.join(a, "ja.wav"), 330)
        tone(os.path.join(a, "ua.wav"), 220, 0.2)
        tone(os.path.join(b, "en.wav"), 220)
        tone(os.path.join(b, "ua.wav"), 220)
        with open(os.path.join(self.tmp, "brief.md"), "w") as f:
            f.write("test brief")
        self.projects = os.path.join(self.tmp, "projects.json")
        with open(self.projects, "w") as f:
            json.dump([{"name": "Test", "path": game, "agent_cwd": game,
                        "agent_brief": os.path.join(self.tmp, "brief.md"), "default_ref": "en"}], f)
        self.data = os.path.join(self.tmp, "data")
        os.makedirs(self.data)
        if settings:
            with open(os.path.join(self.data, "settings.json"), "w") as f:
                json.dump(settings, f)
        fake = os.path.join(HERE, "fake_agent.py")
        os.chmod(fake, 0o755)
        self.port = free_port()
        env = dict(os.environ, SLUHACH_PROJECTS=self.projects, SLUHACH_DATA=self.data,
                   SLUHACH_CLAUDE=fake, PORT=str(self.port), FAKE_MODE=fake_mode)
        self.proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py"), "--no-open"],
                                     cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                if self.get("/api/projects")[0] == 200:
                    break
            except OSError:
                time.sleep(0.1)
        self.pid = self.get("/api/projects")[1][0]["id"]

    def req(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        h = {"Host": f"localhost:{self.port}"}
        data = None
        if body is not None:
            data = body if isinstance(body, (bytes, str)) else json.dumps(body)
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        c.request(method, path, body=data, headers=h)
        r = c.getresponse()
        raw = r.read()
        try:
            out = json.loads(raw)
        except ValueError:
            out = raw
        return r.status, out

    def get(self, path, **kw):
        return self.req("GET", path, **kw)

    def post(self, path, body, **kw):
        return self.req("POST", path, body, **kw)

    def wait_job(self, job_id, timeout=40):
        end = time.time() + timeout
        while time.time() < end:
            jobs = self.get("/api/queue")[1]["jobs"]
            j = next(x for x in jobs if x["id"] == job_id)
            if j["status"] in ("done", "error", "cancelled"):
                return j
            time.sleep(0.3)
        raise AssertionError("job did not finish")

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        shutil.rmtree(self.tmp, ignore_errors=True)


class SecurityAndPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Server()

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def test_page_and_static(self):
        st, body = self.s.get("/")
        self.assertEqual(st, 200)
        self.assertIn(b"/static/app.css", body)
        self.assertEqual(self.s.get("/static/app.css")[0], 200)
        self.assertEqual(self.s.get("/static/js/boot.js")[0], 200)
        self.assertEqual(self.s.get("/static/../server.py")[0], 404)
        self.assertEqual(self.s.get("/static/%2e%2e/server.py")[0], 404)

    def test_foreign_host_rejected(self):
        self.assertEqual(self.s.get("/api/projects", headers={"Host": "evil.example:80"})[0], 403)

    def test_foreign_origin_rejected(self):
        st, _ = self.s.post("/api/state", {"last_project": "x"}, headers={"Origin": "https://evil.example"})
        self.assertEqual(st, 403)

    def test_simple_form_post_rejected(self):
        # a cross-site page can send text/plain without a CORS preflight — must be refused
        st, _ = self.s.post("/api/state", '{"last_project": "x"}', headers={"Content-Type": "text/plain"})
        self.assertEqual(st, 403)

    def test_own_origin_allowed(self):
        st, _ = self.s.post("/api/state", {"last_project": "x"},
                            headers={"Origin": f"http://localhost:{self.s.port}"})
        self.assertEqual(st, 200)

    def test_config(self):
        st, c = self.s.get("/api/config")
        self.assertEqual(st, 200)
        self.assertIn("en", c["source_tags"])
        self.assertIn("ua", c["target_tags"])
        self.assertEqual(c["lang_alias"]["jpn"], "ja")

    def test_scan_and_feedback_ref(self):
        st, d = self.s.get("/api/project?p=" + self.s.pid)
        self.assertEqual(st, 200)
        items = {it["id"]: it for it in d["items"]}
        self.assertEqual(sorted(f["tag"] for f in items["grp/01_a"]["files"]), ["en", "ja", "ua"])
        st, _ = self.s.post("/api/feedback?p=" + self.s.pid, {"items": {"grp/01_a": {"ref": "ja", "heard": True}}})
        self.assertEqual(st, 200)
        fb = self.s.get("/api/project?p=" + self.s.pid)[1]["feedback"]
        self.assertEqual(fb["grp/01_a"]["ref"], "ja")
        self.s.post("/api/feedback?p=" + self.s.pid, {"items": {"grp/01_a": {"ref": "../x"}}})
        fb = self.s.get("/api/project?p=" + self.s.pid)[1]["feedback"]
        self.assertNotIn("ref", fb.get("grp/01_a", {}))


class AgentJobs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Server("edit")

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def test_job_with_reference_check_and_before(self):
        st, r = self.s.post("/api/queue/add?p=" + self.s.pid, {"item": "grp/01_a", "comment": "тест", "ref": "ja"})
        self.assertEqual(st, 200)
        self.assertEqual(r["job"]["ref"], "ja")
        self.assertEqual(r["job"]["ref_file"], "grp/01_a/ja.wav")
        j = self.s.wait_job(r["job"]["id"])
        self.assertEqual(j["status"], "done")
        c = j["check"]
        self.assertTrue(c["changed"])
        self.assertEqual(c["ref_lang"], "ja")
        # fake agent wrote ja.wav pitched up 1.5× → ~495 Hz vs 330 Hz reference: must be flagged
        self.assertTrue(any("висота" in w for w in c["warnings"]), c)
        st, raw = self.s.get("/api/before?id=" + j["id"])
        self.assertEqual(st, 200)
        self.assertTrue(raw[:4] == b"RIFF")
        # ⌘Z restores the version before the agent's edit
        st, h = self.s.post("/api/audio-undo?p=" + self.s.pid, {"f": "grp/01_a/ua.wav"})
        self.assertEqual(st, 200, h)

    def test_default_and_no_reference(self):
        st, r = self.s.post("/api/queue/add?p=" + self.s.pid, {"item": "grp/02_b", "comment": "x"})
        self.assertEqual(r["job"]["ref"], "en")
        self.s.wait_job(r["job"]["id"])
        st, r = self.s.post("/api/queue/add?p=" + self.s.pid, {"item": "grp/02_b", "comment": "y", "ref": "none"})
        self.assertIsNone(r["job"]["ref"])
        self.assertIsNone(r["job"]["ref_file"])
        self.s.wait_job(r["job"]["id"])


class TokenLimit(unittest.TestCase):
    def test_job_stopped_over_limit(self):
        s = Server("burn", settings={"max_job_tokens": 1000})
        try:
            st, r = s.post("/api/queue/add?p=" + s.pid, {"item": "grp/01_a", "comment": "x"})
            j = s.wait_job(r["job"]["id"])
            self.assertEqual(j["status"], "error")
            self.assertIn("ліміт", j["result"])
            self.assertFalse(j["check"]["changed"])
        finally:
            s.close()


class Pitch(unittest.TestCase):
    def test_pitch_of_tones(self):
        import agents
        import analysis
        d = tempfile.mkdtemp()
        try:
            for f in (150, 300, 520):
                p = os.path.join(d, f"{f}.wav")
                tone(p, f)
                got = analysis.pitch(agents.FFMPEG, p)
                self.assertAlmostEqual(got, f, delta=f * 0.05)
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
