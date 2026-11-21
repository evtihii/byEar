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


if __name__ == "__main__":
    unittest.main()
