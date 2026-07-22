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


class HomeFixture:
    """Monta um HOME temporário com dirs de conta; sem herdar TestCase."""

    def _home_with(self, dirs_with_creds, codex=False):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        for d, has_creds in dirs_with_creds.items():
            full = os.path.join(home, d)
            os.makedirs(full)
            if has_creds:
                with open(os.path.join(full, ".credentials.json"), "w") as f:
                    json.dump({"claudeAiOauth": {"accessToken": "x"}}, f)
        if codex:
            full = os.path.join(home, ".codex")
            os.makedirs(full)
            with open(os.path.join(full, "auth.json"), "w") as f:
                json.dump({"tokens": {"access_token": "x"}}, f)
        return home


class TestDiscover(HomeFixture, unittest.TestCase):
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

    def test_all_claude_accounts_have_claude_provider(self):
        home = self._home_with({".claude": True, ".claude-edge": True})
        self.assertEqual([a.provider for a in accounts.discover(home)], ["claude", "claude"])


class TestCodexPrecedence(HomeFixture, unittest.TestCase):
    def test_codex_takes_over_personal_and_hides_claude(self):
        home = self._home_with(
            {".claude": True, ".claude-edge": True, ".claude-sulivam": True}, codex=True
        )
        accs = accounts.discover(home)
        self.assertEqual([a.label for a in accs], ["Pessoal", "Edge", "Sulivam"])
        self.assertEqual([a.provider for a in accs], ["codex", "claude", "claude"])
        self.assertTrue(accs[0].credentials_path.endswith("/.codex/auth.json"))

    def test_personal_falls_back_to_claude_without_codex_login(self):
        home = self._home_with({".claude": True, ".claude-edge": True}, codex=False)
        accs = accounts.discover(home)
        self.assertEqual([(a.label, a.provider) for a in accs],
                         [("Pessoal", "claude"), ("Edge", "claude")])

    def test_codex_alone_is_the_only_account(self):
        home = self._home_with({}, codex=True)
        accs = accounts.discover(home)
        self.assertEqual([(a.label, a.provider) for a in accs], [("Pessoal", "codex")])

    def test_codex_dir_without_auth_json_is_not_an_account(self):
        home = self._home_with({".claude": True})
        os.makedirs(os.path.join(home, ".codex"))
        accs = accounts.discover(home)
        self.assertEqual([(a.label, a.provider) for a in accs], [("Pessoal", "claude")])
