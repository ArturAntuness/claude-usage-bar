"""Estado + orquestração do refresh multi-conta (sem dependência de GTK)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from . import credentials as cred
from . import claude_probe as probe
from . import codex_probe
from .accounts import Account, CODEX
from .credentials import Credentials, CredentialsError
from .usage import Usage, ProbeError


@dataclass
class AccountUsage:
    account: Account
    usage: Usage | None = None
    error: str | None = None


def refresh_account(
    account: Account,
    read: Callable[[str], Credentials] = cred.read,
    prober: Callable[[Credentials], Usage] = probe.fetch,
    now: Callable[[], float] = time.time,
    codex_prober: Callable[[], Usage] = codex_probe.fetch,
) -> AccountUsage:
    """Lê a credencial da conta, faz o probe, devolve o resultado. Nunca levanta."""
    if account.provider == CODEX:
        # O app-server do Codex cuida do token sozinho — não há credencial a validar.
        try:
            return AccountUsage(account, codex_prober(), None)
        except ProbeError as e:
            return AccountUsage(account, None, e.message)

    try:
        c = read(account.credentials_path)
    except CredentialsError as e:
        return AccountUsage(account, None, str(e))

    if cred.is_expired(c.expires_at_ms, now=now()):
        return AccountUsage(account, None, "token expirado — rode o CLI desta conta")

    try:
        return AccountUsage(account, prober(c), None)
    except ProbeError as e:
        return AccountUsage(account, None, e.message)


@dataclass
class MultiModel:
    accounts: list[Account]
    results: list[AccountUsage] = field(default_factory=list)
    last_updated: float | None = None
    is_loading: bool = False

    def run_refresh(
        self,
        read: Callable[[str], Credentials] = cred.read,
        prober: Callable[[Credentials], Usage] = probe.fetch,
        now: Callable[[], float] = time.time,
        codex_prober: Callable[[], Usage] = codex_probe.fetch,
    ) -> None:
        self.results = [refresh_account(a, read, prober, now, codex_prober) for a in self.accounts]
        self.last_updated = now()
