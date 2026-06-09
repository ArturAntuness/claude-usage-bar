"""Estado + orquestração do refresh multi-conta (sem dependência de GTK)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from . import credentials as cred
from . import claude_probe as probe
from .accounts import Account
from .claude_probe import Usage, ProbeError
from .credentials import Credentials, CredentialsError


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
) -> AccountUsage:
    """Lê a credencial da conta, faz o probe, devolve o resultado. Nunca levanta."""
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
    ) -> None:
        self.results = [refresh_account(a, read, prober, now) for a in self.accounts]
        self.last_updated = now()
