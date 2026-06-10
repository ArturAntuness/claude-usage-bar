"""Detecção de cruzamento de limites (puro) + disparo de notificação do GNOME."""
from __future__ import annotations

import subprocess

DEFAULT_THRESHOLDS = (80, 95)


def crossings(prev_pct, curr_pct, thresholds=DEFAULT_THRESHOLDS):
    """Limiares cruzados na SUBIDA: prev < t <= curr."""
    return [t for t in thresholds if prev_pct < t <= curr_pct]


def notifications_to_fire(prev, curr, thresholds=DEFAULT_THRESHOLDS):
    """Mensagens a notificar comparando o refresh anterior com o atual.

    prev/curr: list[AccountUsage]. Só notifica na subida; conta sem dado anterior
    (baseline) ou sem dado atual é ignorada — evita spam no startup.
    """
    prev_by = {r.account.label: r for r in prev}
    msgs = []
    for r in curr:
        if not r.usage:
            continue
        p = prev_by.get(r.account.label)
        if not p or not p.usage:
            continue
        windows = [
            ("5h", p.usage.five_hour_pct, r.usage.five_hour_pct),
            ("7d", p.usage.seven_day_pct, r.usage.seven_day_pct),
        ]
        for win, pv, cv in windows:
            crossed = crossings(pv, cv, thresholds)
            if crossed:
                suffix = " — quase no limite" if max(crossed) >= 95 else ""
                msgs.append(f"{r.account.label} {win} em {cv:.0f}%{suffix}")
    return msgs


# --- disparo (camada de sistema, não testada por unidade) ---
_NOTIFY = None


def _backend():
    global _NOTIFY
    if _NOTIFY is not None:
        return _NOTIFY
    try:
        import gi
        gi.require_version("Notify", "0.7")
        from gi.repository import Notify
        Notify.init("claude-usage-bar")
        _NOTIFY = Notify
    except Exception:
        _NOTIFY = False
    return _NOTIFY


def send(title: str, body: str) -> None:
    """Mostra uma notificação do GNOME (libnotify; fallback notify-send)."""
    backend = _backend()
    if backend:
        try:
            backend.Notification.new(title, body).show()
            return
        except Exception:
            pass
    try:
        subprocess.run(["notify-send", title, body], check=False)
    except Exception:
        pass
