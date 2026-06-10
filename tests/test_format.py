import unittest
from claude_usage_bar import format as fmt


class TestParsePercent(unittest.TestCase):
    def test_fraction(self):
        self.assertEqual(fmt.parse_percent("0.41"), 41.0)

    def test_percent(self):
        self.assertEqual(fmt.parse_percent("41"), 41.0)

    def test_decimal_percent(self):
        self.assertEqual(fmt.parse_percent("85.5"), 85.5)

    def test_one_is_fraction(self):
        self.assertEqual(fmt.parse_percent("1"), 100.0)

    def test_zero(self):
        self.assertEqual(fmt.parse_percent("0"), 0.0)

    def test_invalid(self):
        self.assertEqual(fmt.parse_percent(""), 0.0)
        self.assertEqual(fmt.parse_percent("abc"), 0.0)
        self.assertEqual(fmt.parse_percent(None), 0.0)


class TestResetText(unittest.TestCase):
    NOW = 1_000_000.0

    def test_none(self):
        self.assertEqual(fmt.reset_text(None, now=self.NOW), "")

    def test_past(self):
        self.assertEqual(fmt.reset_text(self.NOW - 10, now=self.NOW), "reset agora")

    def test_minutes(self):
        self.assertEqual(fmt.reset_text(self.NOW + 90, now=self.NOW), "reset 1m")

    def test_hours(self):
        self.assertEqual(fmt.reset_text(self.NOW + 5000, now=self.NOW), "reset 1h23m")

    def test_days(self):
        self.assertEqual(fmt.reset_text(self.NOW + 360000, now=self.NOW), "reset 4d4h")


class TestBarUnicode(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(fmt.bar_unicode(0), "░░░░░░░")

    def test_partial(self):
        self.assertEqual(fmt.bar_unicode(41), "███░░░░")

    def test_full(self):
        self.assertEqual(fmt.bar_unicode(100), "███████")


class TestLevel(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(fmt.level(79), "ok")

    def test_warn(self):
        self.assertEqual(fmt.level(80), "warn")

    def test_crit(self):
        self.assertEqual(fmt.level(95), "crit")


class TestInitial(unittest.TestCase):
    def test_first_letter_upper(self):
        self.assertEqual(fmt.initial("Pessoal"), "P")
        self.assertEqual(fmt.initial("edge"), "E")

    def test_empty(self):
        self.assertEqual(fmt.initial(""), "?")


class TestFormatBar(unittest.TestCase):
    def test_three_accounts(self):
        items = [("Pessoal", 4, 4), ("Edge", 48, 11), ("Sulivam", 12, 20)]
        self.assertEqual(fmt.format_bar(items), "P 4/4  E 48/11  S 12/20")

    def test_none_values(self):
        self.assertEqual(fmt.format_bar([("Edge", None, None)]), "E -/-")

    def test_single_account(self):
        self.assertEqual(fmt.format_bar([("Pessoal", 16, 18)]), "P 16/18")

    def test_rounds(self):
        self.assertEqual(fmt.format_bar([("Pessoal", 4.6, 3.2)]), "P 5/3")


class TestBarSingle(unittest.TestCase):
    def test_values(self):
        self.assertEqual(fmt.bar_single(16, 18), "5h 16%  7d 18%")

    def test_rounds(self):
        self.assertEqual(fmt.bar_single(4.6, 3.2), "5h 5%  7d 3%")

    def test_none(self):
        self.assertEqual(fmt.bar_single(None, None), "5h -  7d -")
