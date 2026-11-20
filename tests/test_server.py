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
from pathlib import Path

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
                        "agent_brief": os.path.join(self.tmp, "brief.md"), "default_ref": "en",
                        "usage_cmd": [sys.executable, os.path.join(HERE, "fake_usage.py")],
                        "usage_label": "FakeLabs"}], f)
        self.data = os.path.join(self.tmp, "data")
        os.makedirs(self.data)
        if settings:
            with open(os.path.join(self.data, "settings.json"), "w") as f:
                json.dump(settings, f)
        fake = os.path.join(HERE, "fake_agent.py")
        os.chmod(fake, 0o755)
        self.port = free_port()
        env = dict(os.environ, SLUHACH_PROJECTS=self.projects, SLUHACH_DATA=self.data,
                   SLUHACH_CLAUDE=fake, PORT=str(self.port), FAKE_MODE=fake_mode,
                   FAKE_USAGE_FILE=os.path.join(self.tmp, "usage.txt"))
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

    def test_reveal_refuses_outside_and_missing(self):
        # (valid paths would open Finder, so only the refusals are tested)
        self.assertEqual(self.s.post("/api/reveal?p=" + self.s.pid, {"f": "../../etc"})[0], 404)
        self.assertEqual(self.s.post("/api/reveal?p=" + self.s.pid, {"f": "grp/nope", "open": True})[0], 404)

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

    def test_generation_credits(self):
        st, u = self.s.get("/api/usage?p=" + self.s.pid + "&fresh=1")
        self.assertEqual(st, 200)
        self.assertEqual(u["usage"]["label"], "FakeLabs")
        self.assertEqual(u["usage"]["limit"], 100000)
        st, r = self.s.post("/api/queue/add?p=" + self.s.pid, {"item": "grp/02_b", "comment": "кредити"})
        j = self.s.wait_job(r["job"]["id"])
        self.assertEqual(j["usage"]["label"], "FakeLabs")
        self.assertEqual(j["usage"]["spent"], 340)
        self.assertEqual(j["usage"]["left"], 100000 - j["usage"]["spent"] - (u["usage"]["used"]))

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


class CancelFromLine(unittest.TestCase):
    """Accidental «Fix»: a queued job and a running job can both be cancelled."""

    def test_cancel_running_and_queued(self):
        s = Server("burn", settings={"max_job_tokens": 0})       # the agent never finishes on its own
        try:
            r1 = s.post("/api/queue/add?p=" + s.pid, {"item": "grp/01_a", "comment": "a"})[1]["job"]
            r2 = s.post("/api/queue/add?p=" + s.pid, {"item": "grp/02_b", "comment": "b"})[1]["job"]
            end = time.time() + 20
            while time.time() < end:
                jobs = {j["id"]: j for j in s.get("/api/queue")[1]["jobs"]}
                if jobs[r1["id"]]["status"] == "running":
                    break
                time.sleep(0.2)
            self.assertEqual(jobs[r2["id"]]["status"], "queued")
            self.assertTrue(s.post("/api/queue/cancel", {"id": r2["id"]})[1]["ok"])
            self.assertTrue(s.post("/api/queue/cancel", {"id": r1["id"]})[1]["ok"])
            j1 = s.wait_job(r1["id"])
            self.assertEqual(j1["status"], "cancelled")
            jobs = {j["id"]: j for j in s.get("/api/queue")[1]["jobs"]}
            self.assertEqual(jobs[r2["id"]]["status"], "cancelled")
            # the agent is free again: a new job gets picked up
            r3 = s.post("/api/queue/add?p=" + s.pid, {"item": "grp/02_b", "comment": "c"})[1]["job"]
            end = time.time() + 20
            while time.time() < end and {j["id"]: j for j in s.get("/api/queue")[1]["jobs"]}[r3["id"]]["status"] != "running":
                time.sleep(0.2)
            self.assertEqual({j["id"]: j for j in s.get("/api/queue")[1]["jobs"]}[r3["id"]]["status"], "running")
            s.post("/api/queue/cancel", {"id": r3["id"]})
        finally:
            s.close()


class Tempo(unittest.TestCase):
    """Tempo change without pitch change: whole file, a region, fit to the reference, undo."""

    @classmethod
    def setUpClass(cls):
        cls.s = Server("noop")

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def edit(self, body):
        body = dict({"f": "grp/01_a/ua.wav", "op": "tempo"}, **body)
        return self.s.post("/api/audio-edit?p=" + self.s.pid, body)

    def measure(self):
        import agents
        import analysis
        full = os.path.join(self.s.tmp, "game", "grp", "01_a", "ua.wav")
        return analysis.measure(agents.FFMPEG, agents._measure, agents._duration, full)

    def undo(self):
        st, _ = self.s.post("/api/audio-undo?p=" + self.s.pid, {"f": "grp/01_a/ua.wav"})
        self.assertEqual(st, 200)

    def test_whole_file_faster_same_pitch(self):
        m0 = self.measure()
        st, r = self.edit({"speed": 1.25})
        self.assertEqual(st, 200, r)
        m1 = self.measure()
        self.assertAlmostEqual(m1["dur"], m0["dur"] / 1.25, delta=0.05)
        self.assertAlmostEqual(m1["f0"], m0["f0"], delta=m0["f0"] * 0.05)
        self.undo()
        self.assertAlmostEqual(self.measure()["dur"], m0["dur"], delta=0.01)

    def test_region_longer(self):
        m0 = self.measure()
        st, r = self.edit({"speed": 0.8, "start": 0.5, "end": 1.5})
        self.assertEqual(st, 200, r)
        # 1 s region at 0.8× → 1.25 s; two 10 ms seams
        self.assertAlmostEqual(self.measure()["dur"], m0["dur"] + 0.25 - 0.02, delta=0.03)
        self.undo()

    def test_fit_reference(self):
        # ua.wav and en.wav are both 2 s: make ua 3 s first, then fit back to the reference
        self.edit({"length": 3.0})
        self.assertAlmostEqual(self.measure()["dur"], 3.0, delta=0.05)
        st, r = self.edit({"fit_ref": True, "ref": "grp/01_a/en.wav"})
        self.assertEqual(st, 200, r)
        self.assertAlmostEqual(self.measure()["dur"], 2.0, delta=0.05)
        self.undo()
        self.undo()

    def test_out_of_range_rejected_without_history(self):
        st, r = self.edit({"speed": 3.5})
        self.assertEqual(st, 400)
        st, h = self.s.post("/api/audio-history?p=" + self.s.pid, {"f": "grp/01_a/ua.wav"})
        if st == 200:
            self.assertEqual(h.get("history", h).get("undo", 0), 0)


class CompareRule(unittest.TestCase):
    """Pitch vs the version before the edit (same voice); loudness/length vs the reference."""

    def test_other_actor_pitch_is_not_a_warning(self):
        import analysis
        new = {"f0": 320, "lufs": -20.0, "dur": 2.5}
        before = {"f0": 318, "lufs": -21.0, "dur": 3.3}
        ref = {"f0": 236, "lufs": -20.0, "dur": 2.4}          # English actress, lower voice
        self.assertEqual(analysis.compare(new, ref, before), [])

    def test_changed_voice_is_a_warning(self):
        import analysis
        w = analysis.compare({"f0": 409, "lufs": -20, "dur": 2.4}, {"f0": 516, "lufs": -20, "dur": 2.4},
                             {"f0": 303, "lufs": -20, "dur": 2.4})
        self.assertEqual(len(w), 1)
        self.assertIn("висота", w[0])

    def test_loudness_and_length_vs_reference(self):
        import analysis
        w = analysis.compare({"f0": 300, "lufs": -27, "dur": 3.5}, {"f0": 200, "lufs": -20, "dur": 2.5},
                             {"f0": 300, "lufs": -27, "dur": 3.5})
        self.assertEqual(len(w), 2)

    def test_without_reference_only_pitch(self):
        import analysis
        self.assertEqual(len(analysis.compare({"f0": 450, "lufs": -40, "dur": 9}, None,
                                              {"f0": 300, "lufs": -20, "dur": 2})), 1)


class Echo(unittest.TestCase):
    """Echo: same length, same loudness of the words, an audible tail; region only; range check; undo."""

    def setUp(self):
        import agents
        self.ff = agents.FFMPEG
        self.d = tempfile.mkdtemp()
        self.src = os.path.join(self.d, "src.wav")
        # 1 s tone burst + 1.5 s silence, so the echo tail has room
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=300:duration=1:sample_rate=48000", "-af", "volume=0.3,apad=pad_dur=1.5",
                        "-ac", "1", "-c:a", "pcm_s16le", self.src], check=True)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def rms(self, f, a, b):
        import echo
        return echo._rms(self.ff, f, a, b)

    def test_whole_file(self):
        import agents
        import echo
        out = os.path.join(self.d, "out.wav")
        echo.add(self.ff, self.src, out, 40, 1.0, total=2.5)
        self.assertAlmostEqual(agents._duration(out), agents._duration(self.src), delta=0.01)
        self.assertAlmostEqual(self.rms(out, 0.1, 0.9), self.rms(self.src, 0.1, 0.9), delta=1.5)
        self.assertLess(self.rms(self.src, 1.2, 1.5), -100)          # silence before
        self.assertGreater(self.rms(out, 1.2, 1.5), -60)             # audible tail after

    def test_more_amount_longer_tail(self):
        import echo
        a, b = os.path.join(self.d, "a.wav"), os.path.join(self.d, "b.wav")
        echo.add(self.ff, self.src, a, 15, 0.5, total=2.5)
        echo.add(self.ff, self.src, b, 70, 2.0, total=2.5)
        self.assertGreater(self.rms(b, 1.4, 1.8), self.rms(a, 1.4, 1.8) + 10)

    def test_region_only(self):
        import echo
        out = os.path.join(self.d, "r.wav")
        echo.add(self.ff, self.src, out, 60, 0.4, start=0.6, end=1.0, total=2.5)
        self.assertAlmostEqual(self.rms(out, 0.1, 0.5), self.rms(self.src, 0.1, 0.5), delta=0.3)   # before region untouched
        self.assertGreater(self.rms(out, 1.05, 1.3), -70)

    def test_range_checked(self):
        import echo
        with self.assertRaises(ValueError):
            echo.add(self.ff, self.src, os.path.join(self.d, "x.wav"), 0, 1)
        with self.assertRaises(ValueError):
            echo.add(self.ff, self.src, os.path.join(self.d, "x.wav"), 30, 9)


class EchoApi(unittest.TestCase):
    def test_echo_and_undo(self):
        s = Server("noop")
        try:
            st, r = s.post("/api/audio-edit?p=" + s.pid, {"f": "grp/01_a/ua.wav", "op": "echo", "amount": 30, "tail": 1})
            self.assertEqual(st, 200, r)
            self.assertEqual(r["info"]["history"]["undo"], 1)
            st, r = s.post("/api/audio-edit?p=" + s.pid, {"f": "grp/01_a/ua.wav", "op": "echo", "amount": 300, "tail": 1})
            self.assertEqual(st, 400)
            st, h = s.post("/api/audio-undo?p=" + s.pid, {"f": "grp/01_a/ua.wav"})
            self.assertEqual(st, 200)
            self.assertEqual(h["history"]["undo"], 0)
        finally:
            s.close()


class Dictation(unittest.TestCase):
    """Local Whisper dictation: status, refusal without a model, end-to-end with an English model if present."""
    EN_MODEL = os.path.expanduser("~/.cache/whisper/ggml-base.en.bin")

    def test_unavailable_without_model(self):
        s = Server("noop", settings={"whisper_model": "/nonexistent/ggml-x.bin"})
        try:
            st, d = s.get("/api/dictation")
            self.assertEqual(st, 200)
            self.assertFalse(d["available"])
            self.assertTrue(d["reason"])
            st, r = s.post("/api/dictate", {"audio": "AAAA", "ext": "wav"})
            self.assertEqual(st, 400)
        finally:
            s.close()

    def test_english_model_is_not_used_for_ukrainian(self):
        import dictation
        d = tempfile.mkdtemp()
        try:
            open(os.path.join(d, "ggml-base.en.bin"), "wb").close()
            old = dictation.MODEL_DIRS
            dictation.MODEL_DIRS = [d]
            try:
                m, note = dictation.find_model({}, "uk")
                self.assertIsNone(m)
                self.assertIn(".en.bin", note)
                m, _ = dictation.find_model({}, "en")
                self.assertTrue(m.endswith("ggml-base.en.bin"))
            finally:
                dictation.MODEL_DIRS = old
        finally:
            shutil.rmtree(d, ignore_errors=True)

    @unittest.skipUnless(shutil.which("whisper-cli") and shutil.which("say")
                         and os.path.isfile(os.path.expanduser("~/.cache/whisper/ggml-base.en.bin")),
                         "needs whisper-cli, say and the base.en model")
    def test_end_to_end_english(self):
        import base64
        d = tempfile.mkdtemp()
        s = Server("noop", settings={"whisper_model": self.EN_MODEL, "dictation_lang": "en"})
        try:
            f = os.path.join(d, "v.aiff")
            subprocess.run(["say", "-o", f, "The voice is too quiet at the end."], check=True)
            st, d1 = s.get("/api/dictation")
            self.assertTrue(d1["available"], d1)
            st, r = s.post("/api/dictate", {"audio": base64.b64encode(Path(f).read_bytes()).decode(), "ext": "aiff"})
            self.assertEqual(st, 200, r)
            self.assertIn("quiet", r["text"].lower())
        finally:
            s.close()
            shutil.rmtree(d, ignore_errors=True)

    def test_docs_pages(self):
        s = Server("noop")
        try:
            st, body = s.get("/docs/")
            self.assertEqual(st, 200)
            self.assertIn("whisper.html".encode(), body)
            st, body = s.get("/docs/whisper.html")
            self.assertEqual(st, 200)
            self.assertIn("brew install whisper-cpp".encode(), body)
            self.assertEqual(s.get("/docs/../server.py")[0], 404)
            self.assertEqual(s.get("/static/docs/../../server.py")[0], 404)
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
