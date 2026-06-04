"""Leitura read-only das credenciais OAuth do Claude Code (~/.claude/.credentials.json)."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

DEFAULT_PATH = os.path.expanduser("~/.claude/.credentials.json")


@dataclass
class Credentials:
    access_token: str
    expires_at_ms: float | None


class CredentialsError(Exception):
    pass


def read(path: str | None = None) -> Credentials:
    p = path or DEFAULT_PATH
    try:
        with open(p, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        raise CredentialsError("credencial não encontrada — faça login no Claude Code")
    except OSError as e:
        raise CredentialsError(f"erro ao ler credencial: {e}")

    try:
        root = json.loads(data)
    except json.JSONDecodeError:
        raise CredentialsError("credencial em formato inesperado")

    oauth = root.get("claudeAiOauth") if isinstance(root, dict) else None
    if not isinstance(oauth, dict):
        raise CredentialsError("credencial em formato inesperado")

    token = oauth.get("accessToken")
    if not isinstance(token, str) or not token:
        raise CredentialsError("credencial sem accessToken")

    exp = oauth.get("expiresAt")
    expires = float(exp) if isinstance(exp, (int, float)) else None
    return Credentials(access_token=token, expires_at_ms=expires)


def is_expired(expires_at_ms: float | None, skew_s: float = 30.0, now: float | None = None) -> bool:
    """True se o token já expirou (com margem skew_s p/ clock skew)."""
    if expires_at_ms is None:
        return False
    if now is None:
        now = time.time()
    return now >= (expires_at_ms / 1000.0) - skew_s
