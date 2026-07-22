"""Probe do Codex via `codex app-server` (JSON-RPC stdio) → rate limits da conta.

Diferente do probe do Claude, não consome cota: `account/rateLimits/read` é uma
leitura, não uma chamada de modelo. O app-server também renova o token sozinho,
então aqui não se lê nem se valida `auth.json`.
"""
from __future__ import annotations

import glob
import json
import os
import queue
import shutil
import subprocess
import threading

from .format import clamp
from .usage import Usage, ProbeError

AUTH_PATH = os.path.expanduser("~/.codex/auth.json")
CODEX_BIN = "codex"
TIMEOUT_S = 20
CLIENT_NAME = "claude-usage-bar"
CLIENT_VERSION = "0.1.0"

# Acima disso a janela é "longa" (semanal); abaixo, "curta" (5h).
SHORT_WINDOW_MAX_MINS = 1440

_INIT_ID = 1
_RATE_LIMITS_ID = 2

# Locais onde o `codex` costuma ficar quando não está no PATH do processo de
# autostart (a sessão GNOME herda um PATH mínimo, sem nvm/pnpm/volta).
_CODEX_GLOBS = (
    "~/.nvm/versions/node/*/bin/codex",
    "~/.local/bin/codex",
    "~/.local/share/pnpm/codex",
    "~/.volta/bin/codex",
    "~/.asdf/shims/codex",
    "/usr/local/bin/codex",
    "/usr/bin/codex",
)


def _resolve_codex_bin() -> str | None:
    """Caminho absoluto do `codex`: primeiro o PATH, depois locais conhecidos.

    Devolve absoluto porque o autostart não tem nvm no PATH — e o próprio
    `codex` é um `.js` com shebang `env node`, então o chamador ainda precisa
    pôr o diretório do binário no PATH do subprocess p/ o `node` vizinho ser achado.
    """
    found = shutil.which(CODEX_BIN)
    if found:
        return found
    for pattern in _CODEX_GLOBS:
        # reverse: entre várias versões de node no nvm, prefere a mais recente
        for match in sorted(glob.glob(os.path.expanduser(pattern)), reverse=True):
            if os.path.isfile(match) and os.access(match, os.X_OK):
                return match
    return None


def _opt_float(raw) -> float | None:
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _window(raw) -> tuple[float, float | None, float | None] | None:
    """`(pct, reset_epoch, duracao_min)` da janela, ou None se ausente/inválida."""
    if not isinstance(raw, dict):
        return None
    pct = _opt_float(raw.get("usedPercent"))
    if pct is None:
        return None
    return clamp(pct), _opt_float(raw.get("resetsAt")), _opt_float(raw.get("windowDurationMins"))


def parse_rate_limits(payload) -> Usage:
    """Converte o `rateLimits` do app-server em `Usage`.

    Classifica cada janela pelo slot que a duração indica. Sem duração, cai na
    convenção histórica do Codex (primary=5h, secondary=semanal). Slot já
    preenchido não é sobrescrito — dois buckets semanais não se anulam.
    """
    if not isinstance(payload, dict):
        raise ProbeError("no_headers", "resposta sem rate limits")

    slots: dict[str, tuple[float, float | None]] = {}
    for key, fallback in (("primary", "five_hour"), ("secondary", "seven_day")):
        win = _window(payload.get(key))
        if win is None:
            continue
        pct, reset, duration = win
        if duration is None:
            slot = fallback
        else:
            slot = "five_hour" if duration <= SHORT_WINDOW_MAX_MINS else "seven_day"
        if slot in slots:
            continue
        slots[slot] = (pct, reset)

    five = slots.get("five_hour")
    seven = slots.get("seven_day")
    return Usage(
        five_hour_pct=five[0] if five else None,
        seven_day_pct=seven[0] if seven else None,
        five_hour_reset_epoch=five[1] if five else None,
        seven_day_reset_epoch=seven[1] if seven else None,
    )


def _pump(stream, out: queue.Queue) -> None:
    try:
        for line in stream:
            out.put(line)
    except Exception:
        pass
    finally:
        out.put(None)


def _rpc_rate_limits(timeout_s: float = TIMEOUT_S) -> dict:
    """Sobe o app-server, faz o handshake e devolve o `rateLimits` cru."""
    codex_bin = _resolve_codex_bin()
    if codex_bin is None:
        raise ProbeError("missing_cli", "CLI do Codex não encontrado — instale ou rode 'codex login'")
    # O diretório do binário entra no PATH: o `codex` é um `.js` com shebang
    # `env node`, e o `node` do nvm mora ao lado dele (fora do PATH do autostart).
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(codex_bin) + os.pathsep + env.get("PATH", "")
    try:
        proc = subprocess.Popen(
            [codex_bin, "app-server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1, env=env,
        )
    except FileNotFoundError:
        raise ProbeError("missing_cli", "CLI do Codex não encontrado no PATH")
    except OSError as e:
        raise ProbeError("transport", f"falha ao iniciar o Codex: {e}")

    lines: queue.Queue = queue.Queue()
    threading.Thread(target=_pump, args=(proc.stdout, lines), daemon=True).start()

    try:
        request = "\n".join(json.dumps(m) for m in (
            {"id": _INIT_ID, "method": "initialize", "params": {"clientInfo": {
                "name": CLIENT_NAME, "title": CLIENT_NAME, "version": CLIENT_VERSION}}},
            {"method": "initialized", "params": {}},
            {"id": _RATE_LIMITS_ID, "method": "account/rateLimits/read", "params": {}},
        )) + "\n"
        try:
            proc.stdin.write(request)
            proc.stdin.flush()
        except OSError:
            raise ProbeError("transport", "Codex encerrou antes de responder")

        while True:
            try:
                line = lines.get(timeout=timeout_s)
            except queue.Empty:
                raise ProbeError("transport", "timeout")
            if line is None:
                raise ProbeError("transport", "Codex encerrou sem responder")
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue  # o app-server também emite linhas de log
            if msg.get("id") != _RATE_LIMITS_ID:
                continue
            if "error" in msg:
                detail = (msg.get("error") or {}).get("message") or "erro do Codex"
                raise ProbeError("rpc", detail)
            return (msg.get("result") or {}).get("rateLimits")
    finally:
        proc.kill()
        proc.wait()


def fetch() -> Usage:
    if not os.path.isfile(AUTH_PATH):
        raise ProbeError("unauthorized", "sem login no Codex — rode 'codex login'")
    return parse_rate_limits(_rpc_rate_limits())
