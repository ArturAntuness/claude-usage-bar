"""Tipos compartilhados pelos probes (Claude e Codex).

Vive fora de `claude_probe` para o probe do Codex não precisar importar de lá.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Usage:
    """Uso das janelas de rate-limit. `None` = a janela não existe no provider.

    O Claude expõe 5h e 7d; planos do Codex podem expor só a semanal.
    """
    five_hour_pct: float | None
    seven_day_pct: float | None
    five_hour_reset_epoch: float | None
    seven_day_reset_epoch: float | None


class ProbeError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message
