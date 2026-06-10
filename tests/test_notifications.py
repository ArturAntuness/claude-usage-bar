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
