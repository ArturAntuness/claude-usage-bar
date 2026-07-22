"""Descoberta das contas: Codex (~/.codex) e Claude (~/.claude, ~/.claude-*)."""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass

CLAUDE = "claude"
CODEX = "codex"

PERSONAL_LABEL = "Pessoal"


@dataclass
class Account:
    label: str
    credentials_path: str            # caminho absoluto do arquivo de credencial
    provider: str = CLAUDE           # CLAUDE | CODEX


def derive_label(dir_basename: str) -> str:
    """`.claude` -> 'Pessoal'; `.claude-edge` -> 'Edge'; `.claude-foo-bar` -> 'Foo-bar'."""
    if dir_basename == ".claude":
        return PERSONAL_LABEL
    suffix = dir_basename[len(".claude-"):] if dir_basename.startswith(".claude-") else dir_basename
    return suffix[:1].upper() + suffix[1:] if suffix else dir_basename


def _codex_account(home: str) -> Account | None:
    auth = os.path.join(home, ".codex", "auth.json")
    if not os.path.isfile(auth):
        return None
    return Account(label=PERSONAL_LABEL, credentials_path=auth, provider=CODEX)


def discover(home: str | None = None) -> list[Account]:
    """Contas do Codex (~/.codex) e do Claude (~/.claude, ~/.claude-*).

    O Codex tem precedência na conta pessoal: havendo `~/.codex/auth.json`, ele é
    a 'Pessoal' e `~/.claude` é ignorado. Sem login no Codex, `~/.claude` volta a
    ser a pessoal sozinho.

    Ordena Pessoal primeiro, depois alfabético por rótulo.
    """
    home = home or os.path.expanduser("~")

    found: list[Account] = []
    codex = _codex_account(home)
    if codex:
        found.append(codex)

    candidates = [os.path.join(home, ".claude")] + sorted(glob.glob(os.path.join(home, ".claude-*")))
    seen: set[str] = set()
    for d in candidates:
        if d in seen or not os.path.isdir(d):
            continue
        seen.add(d)
        label = derive_label(os.path.basename(d))
        if codex and label == PERSONAL_LABEL:
            continue  # o Codex já ocupa a pessoal
        cred = os.path.join(d, ".credentials.json")
        if os.path.isfile(cred):
            found.append(Account(label=label, credentials_path=cred, provider=CLAUDE))

    found.sort(key=lambda a: (a.label != PERSONAL_LABEL, a.label.lower()))
    return found
