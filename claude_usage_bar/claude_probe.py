"""Probe da Messages API com o token OAuth do Claude Code → headers de rate-limit."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Mapping

from .credentials import Credentials
from .format import parse_percent
from .usage import Usage, ProbeError  # re-exportados: importar daqui segue válido

ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OAUTH_BETA = "oauth-2025-04-20"
USER_AGENT = "claude-code/2.1.5"
PROBE_MODEL = "claude-haiku-4-5-20251001"
TIMEOUT_S = 20

H5_UTIL = "anthropic-ratelimit-unified-5h-utilization"
H5_RESET = "anthropic-ratelimit-unified-5h-reset"
H7_UTIL = "anthropic-ratelimit-unified-7d-utilization"
H7_RESET = "anthropic-ratelimit-unified-7d-reset"


def _lower_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {str(k).lower(): v for k, v in headers.items()}


def _opt_float(raw) -> float | None:
    if raw is None:
        return None
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def parse_response(status: int, headers: Mapping[str, str]) -> Usage:
    if status in (401, 403):
        raise ProbeError("unauthorized", "token expirado — rode 'claude' uma vez")

    h = _lower_headers(headers)
    five = h.get(H5_UTIL)
    seven = h.get(H7_UTIL)
    if five is None or seven is None:
        if not (200 <= status <= 299):
            raise ProbeError("http", f"HTTP {status}")
        raise ProbeError("no_headers", "sem headers de rate-limit")

    return Usage(
        five_hour_pct=parse_percent(five),
        seven_day_pct=parse_percent(seven),
        five_hour_reset_epoch=_opt_float(h.get(H5_RESET)),
        seven_day_reset_epoch=_opt_float(h.get(H7_RESET)),
    )


def fetch(creds: Credentials) -> Usage:
    body = json.dumps({
        "model": PROBE_MODEL,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "."}],
    }).encode()

    req = urllib.request.Request(ENDPOINT, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {creds.access_token}")
    req.add_header("anthropic-version", ANTHROPIC_VERSION)
    req.add_header("anthropic-beta", OAUTH_BETA)
    req.add_header("content-type", "application/json")
    req.add_header("User-Agent", USER_AGENT)

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return parse_response(resp.status, dict(resp.headers.items()))
    except urllib.error.HTTPError as e:
        hdrs = dict(e.headers.items()) if e.headers else {}
        return parse_response(e.code, hdrs)
    except urllib.error.URLError as e:
        raise ProbeError("transport", f"rede: {e.reason}")
    except TimeoutError:
        raise ProbeError("transport", "timeout")
