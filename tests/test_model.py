import unittest

from claude_usage_bar.accounts import Account
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
