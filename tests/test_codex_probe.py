import os
import shutil
import tempfile
import unittest
from unittest import mock

from claude_usage_bar import codex_probe
from claude_usage_bar.usage import ProbeError


def window(pct, mins=None, resets=None):
    w = {"usedPercent": pct}
    if mins is not None:
        w["windowDurationMins"] = mins
    if resets is not None:
        w["resetsAt"] = resets
    return w


class TestParseRateLimits(unittest.TestCase):
    def test_weekly_only_plan(self):
        """Payload real do plano prolite: só janela semanal, sem 5h."""
        payload = {
            "limitId": "codex",
            "primary": {"usedPercent": 3, "windowDurationMins": 10080, "resetsAt": 1785084140},
            "secondary": None,
            "planType": "prolite",
        }
        u = codex_probe.parse_rate_limits(payload)
        self.assertIsNone(u.five_hour_pct)
        self.assertIsNone(u.five_hour_reset_epoch)
        self.assertEqual(u.seven_day_pct, 3.0)
        self.assertEqual(u.seven_day_reset_epoch, 1785084140.0)

    def test_five_hour_and_weekly(self):
        payload = {"primary": window(48, 300, 111), "secondary": window(11, 10080, 222)}
        u = codex_probe.parse_rate_limits(payload)
        self.assertEqual((u.five_hour_pct, u.five_hour_reset_epoch), (48.0, 111.0))
        self.assertEqual((u.seven_day_pct, u.seven_day_reset_epoch), (11.0, 222.0))

    def test_five_hour_only(self):
        u = codex_probe.parse_rate_limits({"primary": window(20, 300), "secondary": None})
        self.assertEqual(u.five_hour_pct, 20.0)
        self.assertIsNone(u.seven_day_pct)

    def test_zero_percent_is_data_not_absence(self):
        u = codex_probe.parse_rate_limits({"primary": window(0, 10080)})
        self.assertEqual(u.seven_day_pct, 0.0)
        self.assertIsNotNone(u.seven_day_pct)

    def test_colliding_windows_do_not_overwrite(self):
        """Dois buckets semanais: o primeiro ocupa o slot, o segundo é descartado."""
        u = codex_probe.parse_rate_limits(
            {"primary": window(7, 10080), "secondary": window(99, 10080)}
        )
        self.assertEqual(u.seven_day_pct, 7.0)
        self.assertIsNone(u.five_hour_pct)

    def test_missing_duration_uses_historical_convention(self):
        u = codex_probe.parse_rate_limits({"primary": window(5), "secondary": window(9)})
        self.assertEqual(u.five_hour_pct, 5.0)
        self.assertEqual(u.seven_day_pct, 9.0)

    def test_daily_window_counts_as_short(self):
        u = codex_probe.parse_rate_limits({"primary": window(10, 1440), "secondary": window(5, 10080)})
        self.assertEqual(u.five_hour_pct, 10.0)
        self.assertEqual(u.seven_day_pct, 5.0)

    def test_no_windows(self):
        u = codex_probe.parse_rate_limits({"primary": None, "secondary": None})
        self.assertIsNone(u.five_hour_pct)
        self.assertIsNone(u.seven_day_pct)

    def test_percent_is_clamped(self):
        u = codex_probe.parse_rate_limits({"primary": window(140, 10080)})
        self.assertEqual(u.seven_day_pct, 100.0)

    def test_reset_absent_keeps_percent(self):
        u = codex_probe.parse_rate_limits({"primary": window(42, 10080)})
        self.assertEqual(u.seven_day_pct, 42.0)
        self.assertIsNone(u.seven_day_reset_epoch)

    def test_garbage_percent_is_treated_as_absent(self):
        u = codex_probe.parse_rate_limits({"primary": {"usedPercent": "n/a", "windowDurationMins": 10080}})
        self.assertIsNone(u.seven_day_pct)

    def test_null_payload_raises(self):
        with self.assertRaises(ProbeError) as ctx:
            codex_probe.parse_rate_limits(None)
        self.assertEqual(ctx.exception.kind, "no_headers")

    def test_non_dict_window_is_ignored(self):
        u = codex_probe.parse_rate_limits({"primary": "oops", "secondary": window(4, 10080)})
        self.assertEqual(u.seven_day_pct, 4.0)


class TestFetchGuards(unittest.TestCase):
    def test_missing_auth_file_reports_unauthorized(self):
        original = codex_probe.AUTH_PATH
        codex_probe.AUTH_PATH = "/nao/existe/auth.json"
        self.addCleanup(setattr, codex_probe, "AUTH_PATH", original)
        with self.assertRaises(ProbeError) as ctx:
            codex_probe.fetch()
        self.assertEqual(ctx.exception.kind, "unauthorized")


class TestResolveCodexBin(unittest.TestCase):
    def test_prefers_path(self):
        with mock.patch.object(codex_probe.shutil, "which", return_value="/usr/bin/codex"):
            self.assertEqual(codex_probe._resolve_codex_bin(), "/usr/bin/codex")

    def test_falls_back_to_known_globs(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home)
        nvm_bin = os.path.join(home, ".nvm/versions/node/v20.19.5/bin")
        os.makedirs(nvm_bin)
        codex = os.path.join(nvm_bin, "codex")
        with open(codex, "w") as f:
            f.write("#!/usr/bin/env node\n")
        os.chmod(codex, 0o755)
        with mock.patch.object(codex_probe.shutil, "which", return_value=None), \
             mock.patch.object(codex_probe.os.path, "expanduser",
                               side_effect=lambda p: p.replace("~", home)):
            self.assertEqual(codex_probe._resolve_codex_bin(), codex)

    def test_returns_none_when_nowhere(self):
        empty = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, empty)
        with mock.patch.object(codex_probe.shutil, "which", return_value=None), \
             mock.patch.object(codex_probe.os.path, "expanduser",
                               side_effect=lambda p: p.replace("~", empty)):
            self.assertIsNone(codex_probe._resolve_codex_bin())

    def test_fetch_raises_missing_cli_when_unresolved(self):
        with mock.patch.object(codex_probe.os.path, "isfile", return_value=True), \
             mock.patch.object(codex_probe, "_resolve_codex_bin", return_value=None):
            with self.assertRaises(ProbeError) as ctx:
                codex_probe.fetch()
        self.assertEqual(ctx.exception.kind, "missing_cli")


if __name__ == "__main__":
    unittest.main()
