import json
import os
import tempfile
import unittest

from claude_usage_bar import credentials as cred


class TestRead(unittest.TestCase):
    def _write(self, obj):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f)
        self.addCleanup(os.remove, path)
        return path

    def test_valid(self):
        p = self._write({"claudeAiOauth": {"accessToken": "abc", "expiresAt": 1780592012214}})
        c = cred.read(p)
        self.assertEqual(c.access_token, "abc")
        self.assertEqual(c.expires_at_ms, 1780592012214)

    def test_missing_file(self):
        with self.assertRaises(cred.CredentialsError):
            cred.read("/nonexistent/path/x.json")

    def test_malformed_json(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            f.write("{not json")
        self.addCleanup(os.remove, path)
        with self.assertRaises(cred.CredentialsError):
            cred.read(path)

    def test_no_token(self):
        p = self._write({"claudeAiOauth": {"expiresAt": 123}})
        with self.assertRaises(cred.CredentialsError):
            cred.read(p)

    def test_no_oauth_key(self):
        p = self._write({"something": {}})
        with self.assertRaises(cred.CredentialsError):
            cred.read(p)


class TestExpiry(unittest.TestCase):
    def test_none_never_expires(self):
        self.assertFalse(cred.is_expired(None, now=1_000_000))

    def test_future(self):
        self.assertFalse(cred.is_expired(2_000_000_000_000, now=1_000_000))

    def test_past(self):
        self.assertTrue(cred.is_expired(1_000_000_000, now=2_000_000))

    def test_skew(self):
        exp_ms = (1_000_000 + 10) * 1000  # expira em 10s
        self.assertTrue(cred.is_expired(exp_ms, skew_s=30, now=1_000_000))
