import unittest

from claude_usage_bar.claude_probe import parse_response, ProbeError

H5U = "anthropic-ratelimit-unified-5h-utilization"
H5R = "anthropic-ratelimit-unified-5h-reset"
H7U = "anthropic-ratelimit-unified-7d-utilization"
H7R = "anthropic-ratelimit-unified-7d-reset"


class TestParseResponse(unittest.TestCase):
    def test_ok_fraction(self):
        u = parse_response(200, {H5U: "0.41", H7U: "0.12", H5R: "1700000000", H7R: "1700500000"})
        self.assertEqual(u.five_hour_pct, 41.0)
        self.assertEqual(u.seven_day_pct, 12.0)
        self.assertEqual(u.five_hour_reset_epoch, 1700000000.0)
        self.assertEqual(u.seven_day_reset_epoch, 1700500000.0)

    def test_ok_percent_case_insensitive(self):
        u = parse_response(200, {H5U.upper(): "41", H7U.upper(): "12"})
        self.assertEqual(u.five_hour_pct, 41.0)
        self.assertEqual(u.seven_day_pct, 12.0)
        self.assertIsNone(u.five_hour_reset_epoch)

    def test_429_still_parses(self):
        u = parse_response(429, {H5U: "0.99", H7U: "0.50"})
        self.assertEqual(u.five_hour_pct, 99.0)

    def test_401_unauthorized(self):
        with self.assertRaises(ProbeError) as ctx:
            parse_response(401, {})
        self.assertEqual(ctx.exception.kind, "unauthorized")

    def test_403_unauthorized(self):
        with self.assertRaises(ProbeError) as ctx:
            parse_response(403, {})
        self.assertEqual(ctx.exception.kind, "unauthorized")

    def test_400_no_headers_http(self):
        with self.assertRaises(ProbeError) as ctx:
            parse_response(400, {})
        self.assertEqual(ctx.exception.kind, "http")

    def test_200_no_headers(self):
        with self.assertRaises(ProbeError) as ctx:
            parse_response(200, {})
        self.assertEqual(ctx.exception.kind, "no_headers")
