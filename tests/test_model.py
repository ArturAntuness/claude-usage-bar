import unittest

from claude_usage_bar.model import UsageModel
from claude_usage_bar.credentials import Credentials, CredentialsError
from claude_usage_bar.claude_probe import Usage, ProbeError

FIXED_NOW = 1_000_000.0


def now():
    return FIXED_NOW


def good_creds():
    return Credentials(access_token="t", expires_at_ms=(FIXED_NOW + 3600) * 1000)


class TestModel(unittest.TestCase):
    def test_success(self):
        m = UsageModel()
        u = Usage(41, 12, None, None)
        m.run_refresh(read_creds=good_creds, prober=lambda c: u, now=now)
        self.assertIs(m.usage, u)
        self.assertIsNone(m.error)
        self.assertEqual(m.last_updated, FIXED_NOW)

    def test_credentials_error(self):
        m = UsageModel()

        def bad():
            raise CredentialsError("sem login")

        m.run_refresh(read_creds=bad, prober=lambda c: None, now=now)
        self.assertIsNone(m.usage)
        self.assertEqual(m.error, "sem login")

    def test_expired_token_short_circuits(self):
        m = UsageModel()
        expired = Credentials(access_token="t", expires_at_ms=(FIXED_NOW - 10) * 1000)
        called = {"probe": False}

        def prober(c):
            called["probe"] = True
            return Usage(0, 0, None, None)

        m.run_refresh(read_creds=lambda: expired, prober=prober, now=now)
        self.assertFalse(called["probe"])
        self.assertIn("expirado", m.error)

    def test_probe_error_keeps_message(self):
        m = UsageModel()

        def prober(c):
            raise ProbeError("transport", "timeout")

        m.run_refresh(read_creds=good_creds, prober=prober, now=now)
        self.assertEqual(m.error, "timeout")
