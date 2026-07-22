import unittest

from claude_usage_bar.accounts import Account
from claude_usage_bar.model import AccountUsage
from claude_usage_bar.claude_probe import Usage
from claude_usage_bar import notifications as notif


def au(label, five=None, seven=None, error=None):
    usage = Usage(five, seven, None, None) if five is not None else None
    return AccountUsage(Account(label, f"/{label}"), usage, error)


class TestCrossings(unittest.TestCase):
    def test_cross_80(self):
        self.assertEqual(notif.crossings(70, 85), [80])

    def test_cross_both(self):
        self.assertEqual(notif.crossings(70, 96), [80, 95])

    def test_already_above_no_cross(self):
        self.assertEqual(notif.crossings(85, 90), [])

    def test_below_no_cross(self):
        self.assertEqual(notif.crossings(10, 20), [])

    def test_boundary_inclusive(self):
        self.assertEqual(notif.crossings(79, 80), [80])

    def test_cross_95_only(self):
        self.assertEqual(notif.crossings(81, 96), [95])


class TestNotificationsToFire(unittest.TestCase):
    def test_baseline_no_prev(self):
        self.assertEqual(notif.notifications_to_fire([], [au("Pessoal", 90, 10)]), [])

    def test_rising_cross(self):
        msgs = notif.notifications_to_fire([au("Pessoal", 70, 10)], [au("Pessoal", 85, 10)])
        self.assertEqual(len(msgs), 1)
        self.assertIn("Pessoal", msgs[0])
        self.assertIn("5h", msgs[0])
        self.assertIn("85%", msgs[0])

    def test_no_cross(self):
        self.assertEqual(
            notif.notifications_to_fire([au("Pessoal", 85, 10)], [au("Pessoal", 90, 12)]), []
        )

    def test_expired_curr_skipped(self):
        msgs = notif.notifications_to_fire([au("Pessoal", 70, 10)], [au("Pessoal", error="x")])
        self.assertEqual(msgs, [])

    def test_95_suffix(self):
        msgs = notif.notifications_to_fire([au("Edge", 90, 10)], [au("Edge", 96, 10)])
        self.assertEqual(len(msgs), 1)
        self.assertIn("quase no limite", msgs[0])

    def test_two_accounts_independent(self):
        prev = [au("Pessoal", 70, 10), au("Edge", 10, 10)]
        curr = [au("Pessoal", 81, 10), au("Edge", 12, 12)]
        msgs = notif.notifications_to_fire(prev, curr)
        self.assertEqual(len(msgs), 1)
        self.assertIn("Pessoal", msgs[0])


def codex_au(label, seven):
    """Conta do Codex: sem janela de 5h."""
    return AccountUsage(
        Account(label, f"/{label}", provider="codex"), Usage(None, seven, None, None), None
    )


class TestMissingWindow(unittest.TestCase):
    def test_absent_five_hour_does_not_crash(self):
        msgs = notif.notifications_to_fire([codex_au("Pessoal", 10)], [codex_au("Pessoal", 20)])
        self.assertEqual(msgs, [])

    def test_seven_day_still_notifies_without_five_hour(self):
        msgs = notif.notifications_to_fire([codex_au("Pessoal", 70)], [codex_au("Pessoal", 82)])
        self.assertEqual(len(msgs), 1)
        self.assertIn("7d", msgs[0])
        self.assertIn("Pessoal", msgs[0])

    def test_absent_window_never_reported_as_crossing(self):
        msgs = notif.notifications_to_fire([codex_au("Pessoal", 96)], [codex_au("Pessoal", 97)])
        self.assertEqual(msgs, [])

    def test_mixed_providers(self):
        prev = [codex_au("Pessoal", 70), au("Edge", 70, 10)]
        curr = [codex_au("Pessoal", 85), au("Edge", 90, 10)]
        msgs = notif.notifications_to_fire(prev, curr)
        self.assertEqual(len(msgs), 2)
        self.assertIn("Pessoal 7d", msgs[0])
        self.assertIn("Edge 5h", msgs[1])
