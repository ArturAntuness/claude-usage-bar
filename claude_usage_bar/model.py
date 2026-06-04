"""Estado + orquestração do refresh (sem dependência de GTK)."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from . import credentials as cred
from . import claude_probe as probe
from .claude_probe import Usage, ProbeError
from .credentials import Credentials, CredentialsError


@dataclass
class UsageModel:
    usage: Usage | None = None
    error: str | None = None
    last_updated: float | None = None
    is_loading: bool = False

    def run_refresh(
        self,
        read_creds: Callable[[], Credentials] = cred.read,
        prober: Callable[[Credentials], Usage] = probe.fetch,
        now: Callable[[], float] = time.time,
    ) -> None:
        """Lê credencial, faz o probe, atualiza estado. Nunca levanta — erros vão p/ self.error."""
        try:
            c = read_creds()
        except CredentialsError as e:
            self.usage, self.error = None, str(e)
            self.last_updated = now()
            return

        if cred.is_expired(c.expires_at_ms, now=now()):
            self.usage = None
            self.error = "token expirado — rode 'claude' uma vez"
            self.last_updated = now()
            return

        try:
            self.usage = prober(c)
            self.error = None
        except ProbeError as e:
            self.error = e.message  # mantém self.usage anterior (pode ser stale)
        self.last_updated = now()
