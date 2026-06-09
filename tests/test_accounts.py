import json
import os
import shutil
import tempfile
import unittest

from claude_usage_bar import accounts


class TestDeriveLabel(unittest.TestCase):
    def test_default(self):
        self.assertEqual(accounts.derive_label(".claude"), "Pessoal")

    def test_edge(self):
        self.assertEqual(accounts.derive_label(".claude-edge"), "Edge")

    def test_sulivam(self):
        self.assertEqual(accounts.derive_label(".claude-sulivam"), "Sulivam")

    def test_multiword(self):
        self.assertEqual(accounts.derive_label(".claude-foo-bar"), "Foo-bar")


class TestDiscover(unittest.TestCase):
    def _home_with(self, dirs_with_creds):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        for d, has_creds in dirs_with_creds.items():
            full = os.path.join(home, d)
            os.makedirs(full)
            if has_creds:
                with open(os.path.join(full, ".credentials.json"), "w") as f:
                    json.dump({"claudeAiOauth": {"accessToken": "x"}}, f)
        return home

    def test_three_accounts_sorted(self):
        home = self._home_with({".claude": True, ".claude-edge": True, ".claude-sulivam": True})
        accs = accounts.discover(home)
        self.assertEqual([a.label for a in accs], ["Pessoal", "Edge", "Sulivam"])
        self.assertTrue(accs[0].credentials_path.endswith("/.claude/.credentials.json"))

    def test_ignores_dirs_without_credentials(self):
        home = self._home_with({".claude": True, ".claude-x": False})
        accs = accounts.discover(home)
        self.assertEqual([a.label for a in accs], ["Pessoal"])

    def test_empty(self):
        home = self._home_with({})
        self.assertEqual(accounts.discover(home), [])
