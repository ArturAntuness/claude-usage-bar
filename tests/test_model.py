import unittest

from claude_usage_bar.accounts import Account, CODEX
from claude_usage_bar.model import refresh_account, MultiModel
from claude_usage_bar.credentials import Credentials, CredentialsError
from claude_usage_bar.claude_probe import Usage, ProbeError

FIXED_NOW = 1_000_000.0


def now():
    return FIXED_NOW


def acc(label="Pessoal", path="/fake/.claude/.credentials.json"):
    return Account(label=label, credentials_path=path)


def good_creds():
    return Credentials(access_token="t", expires_at_ms=(FIXED_NOW + 3600) * 1000)


class TestRefreshAccount(unittest.TestCase):
    def test_success(self):
        u = Usage(41, 12, None, None)
        r = refresh_account(acc(), read=lambda p: good_creds(), prober=lambda c: u, now=now)
        self.assertIs(r.usage, u)
        self.assertIsNone(r.error)
        self.assertEqual(r.account.label, "Pessoal")

    def test_credentials_error(self):
        def bad(p):
            raise CredentialsError("sem login")

        r = refresh_account(acc(), read=bad, prober=lambda c: None, now=now)
        self.assertIsNone(r.usage)
        self.assertEqual(r.error, "sem login")

    def test_expired_short_circuits(self):
        expired = Credentials(access_token="t", expires_at_ms=(FIXED_NOW - 10) * 1000)
        called = {"probe": False}

        def prober(c):
            called["probe"] = True
            return Usage(0, 0, None, None)

        r = refresh_account(acc(), read=lambda p: expired, prober=prober, now=now)
        self.assertFalse(called["probe"])
        self.assertIn("expirado", r.error)

    def test_probe_error(self):
        def prober(c):
            raise ProbeError("transport", "timeout")

        r = refresh_account(acc(), read=lambda p: good_creds(), prober=prober, now=now)
        self.assertEqual(r.error, "timeout")

    def test_reads_account_path(self):
        seen = {}

        def read(p):
            seen["path"] = p
            return good_creds()

        refresh_account(
            acc(path="/x/.claude-edge/.credentials.json"),
            read=read, prober=lambda c: Usage(1, 1, None, None), now=now,
        )
        self.assertEqual(seen["path"], "/x/.claude-edge/.credentials.json")


def codex_acc(label="Pessoal"):
    return Account(label=label, credentials_path="/fake/.codex/auth.json", provider=CODEX)


class TestCodexDispatch(unittest.TestCase):
    def test_codex_uses_codex_prober(self):
        u = Usage(None, 3.0, None, 1785084140.0)
        r = refresh_account(codex_acc(), codex_prober=lambda: u)
        self.assertIs(r.usage, u)
        self.assertIsNone(r.error)

    def test_codex_skips_credentials_read(self):
        """O app-server renova o token sozinho — não se lê nem valida auth.json."""
        def read(p):
            raise AssertionError("não deveria ler credencial para o Codex")

        r = refresh_account(codex_acc(), read=read, codex_prober=lambda: Usage(None, 1.0, None, None))
        self.assertIsNotNone(r.usage)

    def test_codex_never_calls_claude_prober(self):
        def prober(c):
            raise AssertionError("não deveria usar o probe do Claude")

        r = refresh_account(codex_acc(), prober=prober, codex_prober=lambda: Usage(None, 2.0, None, None))
        self.assertEqual(r.usage.seven_day_pct, 2.0)

    def test_codex_probe_error_becomes_row_error(self):
        def failing():
            raise ProbeError("missing_cli", "CLI do Codex não encontrado no PATH")

        r = refresh_account(codex_acc(), codex_prober=failing)
        self.assertIsNone(r.usage)
        self.assertEqual(r.error, "CLI do Codex não encontrado no PATH")

    def test_claude_account_never_calls_codex_prober(self):
        def codex_prober():
            raise AssertionError("não deveria usar o probe do Codex")

        r = refresh_account(
            acc(), read=lambda p: good_creds(), prober=lambda c: Usage(1, 2, None, None),
            now=now, codex_prober=codex_prober,
        )
        self.assertIsNotNone(r.usage)

    def test_mixed_providers_in_multimodel(self):
        m = MultiModel(accounts=[codex_acc("Pessoal"), acc("Edge", "/b")])
        m.run_refresh(
            read=lambda p: good_creds(),
            prober=lambda c: Usage(48, 11, None, None),
            now=now,
            codex_prober=lambda: Usage(None, 3.0, None, None),
        )
        self.assertIsNone(m.results[0].usage.five_hour_pct)
        self.assertEqual(m.results[0].usage.seven_day_pct, 3.0)
        self.assertEqual(m.results[1].usage.five_hour_pct, 48)


class TestMultiModel(unittest.TestCase):
    def test_refresh_all_in_order(self):
        m = MultiModel(accounts=[acc("Pessoal", "/a"), acc("Edge", "/b")])
        m.run_refresh(read=lambda p: good_creds(), prober=lambda c: Usage(5, 6, None, None), now=now)
        self.assertEqual([r.account.label for r in m.results], ["Pessoal", "Edge"])
        self.assertEqual(m.last_updated, FIXED_NOW)
        self.assertTrue(all(r.usage for r in m.results))

    def test_mixed_ok_and_error(self):
        m = MultiModel(accounts=[acc("Pessoal", "/a"), acc("Edge", "/b")])

        def read(p):
            if p == "/b":
                raise CredentialsError("edge sem login")
            return good_creds()

        m.run_refresh(read=read, prober=lambda c: Usage(5, 6, None, None), now=now)
        self.assertIsNotNone(m.results[0].usage)
        self.assertEqual(m.results[1].error, "edge sem login")
