"""Descoberta das contas Claude a partir dos config dirs (~/.claude, ~/.claude-*)."""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass


@dataclass
class Account:
    label: str
    credentials_path: str   # caminho absoluto do .credentials.json


def derive_label(dir_basename: str) -> str:
    """`.claude` -> 'Pessoal'; `.claude-edge` -> 'Edge'; `.claude-foo-bar` -> 'Foo-bar'."""
    if dir_basename == ".claude":
        return "Pessoal"
    suffix = dir_basename[len(".claude-"):] if dir_basename.startswith(".claude-") else dir_basename
    return suffix[:1].upper() + suffix[1:] if suffix else dir_basename


def discover(home: str | None = None) -> list[Account]:
    """Contas = dirs `home/.claude` e `home/.claude-*` que tenham `.credentials.json`.

    Ordena Pessoal (~/.claude) primeiro, depois alfabético por rótulo.
    """
    home = home or os.path.expanduser("~")
    candidates = [os.path.join(home, ".claude")] + sorted(glob.glob(os.path.join(home, ".claude-*")))

    found: list[Account] = []
    seen: set[str] = set()
    for d in candidates:
        if d in seen or not os.path.isdir(d):
            continue
        seen.add(d)
        cred = os.path.join(d, ".credentials.json")
        if os.path.isfile(cred):
            found.append(Account(label=derive_label(os.path.basename(d)), credentials_path=cred))

    found.sort(key=lambda a: (a.label != "Pessoal", a.label.lower()))
    return found
