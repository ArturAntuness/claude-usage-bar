from __future__ import annotations

import time


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def parse_percent(raw: str | None) -> float:
    if raw is None:
        return 0.0
    try:
        v = float(str(raw).strip())
    except (TypeError, ValueError):
        return 0.0
    if v <= 1.0:
        v *= 100.0
    return clamp(v)


def reset_text(epoch: float | None, now: float | None = None) -> str:
    if epoch is None:
        return ""
    if now is None:
        now = time.time()
    secs = int(epoch - now)
    if secs <= 0:
        return "reset agora"
    d = secs // 86400
    h = (secs % 86400) // 3600
    m = (secs % 3600) // 60
    if d > 0:
        return f"reset {d}d{h}h"
    if h > 0:
        return f"reset {h}h{m}m"
    return f"reset {m}m"


def bar_unicode(pct: float, cells: int = 7) -> str:
    filled = round(clamp(pct) / 100 * cells)
    filled = max(0, min(cells, filled))
    return "█" * filled + "░" * (cells - filled)


def level(pct: float) -> str:
    if pct >= 95:
        return "crit"
    if pct >= 80:
        return "warn"
    return "ok"
