import os
import tempfile
import unittest

from claude_usage_bar import icon


class TestIcon(unittest.TestCase):
    def _render(self, pct, state):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "g.png")
        icon.render_png(p, pct, state)
        self.addCleanup(lambda: (os.path.exists(p) and os.remove(p), os.rmdir(d)))
        return p

    def test_creates_valid_png(self):
        p = self._render(41, "ok")
        self.assertGreater(os.path.getsize(p), 0)
        with open(p, "rb") as f:
            self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")

    def test_idle(self):
        p = self._render(None, "idle")
        self.assertGreater(os.path.getsize(p), 0)

    def test_full_crit(self):
        p = self._render(100, "crit")
        self.assertGreater(os.path.getsize(p), 0)
