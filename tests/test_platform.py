"""platform_util tests that run the same on macOS and Windows (no dialogs, nothing moved to a real trash)."""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import platform_util  # noqa: E402


class PlatformTest(unittest.TestCase):
    def test_trash_dir(self):
        d = platform_util.trash_dir("Holosii_volume")
        self.assertEqual(os.path.basename(d), "Holosii_volume")
        self.assertEqual(os.path.dirname(d), platform_util.trash_root())
        if platform_util.IS_MAC:
            self.assertEqual(d, os.path.expanduser("~/.Trash/Holosii_volume"))
            self.assertEqual(platform_util.agent_trash_hint(), "")
        if platform_util.IS_WIN:
            self.assertIn(os.path.join("Holosii", "Trash"), d)
            self.assertIn(d.replace("Holosii_volume", "Holosii_agent"), platform_util.agent_trash_hint())

    def test_which(self):
        exe = os.path.basename(sys.executable)
        name = os.path.splitext(exe)[0] if platform_util.IS_WIN else exe   # Windows: found without .exe
        found = platform_util.which(name, extra=[os.path.dirname(sys.executable)])
        self.assertTrue(found and os.path.exists(found), found)
        self.assertIsNone(platform_util.which("holosii-no-such-tool", extra=[]))

    def test_kill_tree(self):
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], **platform_util.new_group_kwargs())
        platform_util.kill_tree(p)
        p.wait(10)
        self.assertIsNotNone(p.returncode)

    def test_recycle_noop(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertTrue(platform_util.recycle([os.path.join(t, "missing")]))   # nothing to move

    @unittest.skipUnless(platform_util.IS_WIN, "Windows Recycle Bin")
    def test_recycle_windows(self):
        with tempfile.TemporaryDirectory() as t:
            f = os.path.join(t, "голос.txt")
            with open(f, "w", encoding="utf-8") as h:
                h.write("x")
            self.assertTrue(platform_util.recycle([f]))
            self.assertFalse(os.path.exists(f))

    def test_stdin_stop(self):
        code = ("import sys, threading; sys.argv.append('--stdin-stop'); import platform_util; "
                "e = threading.Event(); platform_util.on_terminate(e.set); "
                "print('stopped' if e.wait(20) else 'timeout')")
        p = subprocess.Popen([sys.executable, "-c", code], cwd=os.path.dirname(HERE), stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, text=True)
        out, _ = p.communicate("", timeout=30)        # close stdin at once → stop
        self.assertEqual(out.strip(), "stopped")


class ClaudeSettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="holosii_cs_")
        import agents
        self.agents = agents
        self._data = agents.DATA
        agents.DATA = self.tmp

    def tearDown(self):
        self.agents.DATA = self._data
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def read(self, settings):
        import json
        path, note = self.agents.write_claude_settings(settings)
        with open(path, encoding="utf-8") as f:
            return json.load(f), note

    def test_default_no_sandbox(self):
        cfg, note = self.read({})
        self.assertEqual(cfg, {"disableAllHooks": True})
        self.assertEqual(note, "")

    def test_sandbox_opt_in(self):
        cfg, note = self.read({"agent_sandbox": True, "agent_sandbox_domains": ["api.example.com"]})
        if platform_util.IS_WIN:
            self.assertNotIn("sandbox", cfg)
            self.assertIn("Windows", note)
            return
        sb = cfg["sandbox"]
        self.assertTrue(sb["enabled"] and sb["failIfUnavailable"])
        self.assertFalse(sb["allowUnsandboxedCommands"])
        self.assertEqual(sb["network"]["allowedDomains"], ["api.example.com"])
        self.assertIn(platform_util.trash_root(), sb["filesystem"]["allowWrite"])


class TokenTest(unittest.TestCase):
    def test_token_created_once_and_private(self):
        with tempfile.TemporaryDirectory() as t:
            f = os.path.join(t, "sub", "token")
            a = platform_util.load_token(f)
            self.assertGreaterEqual(len(a), 32)
            self.assertEqual(platform_util.load_token(f), a)
            if not platform_util.IS_WIN:
                self.assertEqual(os.stat(f).st_mode & 0o077, 0)
                os.chmod(f, 0o644)
                platform_util.load_token(f)
                self.assertEqual(os.stat(f).st_mode & 0o077, 0)

    def test_open_folder_never_runs_a_file(self):
        calls = []
        orig = platform_util.reveal
        platform_util.reveal = calls.append
        try:
            with tempfile.NamedTemporaryFile(suffix=".bat", delete=False) as f:
                name = f.name
            platform_util.open_folder(name)               # a file → only shown selected, never opened
            self.assertEqual(calls, [os.path.abspath(name)])
        finally:
            platform_util.reveal = orig
            os.remove(name)


if __name__ == "__main__":
    unittest.main()
