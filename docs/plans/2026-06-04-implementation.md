# claude-usage-bar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Indicador de bandeja (system tray) para Ubuntu/GNOME que mostra o uso do plano Claude Code (janelas 5h e 7d) com ícone medidor + menu de detalhe.

**Architecture:** App Python single-process. Funções puras (formatação, parsing de credencial e de resposta) isoladas e 100% testáveis; uma camada GTK (`AyatanaAppIndicator3`) que orquestra refresh em thread, desenha o ícone com Cairo e reconstrói o menu. Token lido read-only de `~/.claude/.credentials.json` (modo passivo).

**Tech Stack:** Python 3, GTK 3 (`gi`), AyatanaAppIndicator3, Cairo, `urllib` (stdlib, sem dependências pip).

**Comandos de teste** (sempre a partir de `/home/artur/pessoal/claude-usage-bar`):
- Suite: `python3 -m unittest discover -s tests -t . -v`
- Um arquivo: `python3 -m unittest tests.test_format -v`

---

### Task 0: Esqueleto do projeto + dependências de sistema

**Files:**
- Create: `claude_usage_bar/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Instalar dependências de sistema**

Run:
```bash
sudo apt-get update -qq && sudo apt-get install -y \
  python3-gi python3-gi-cairo python3-cairo \
  gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
```
Expected: instala sem erro (pode pedir senha do sudo).

- [ ] **Step 2: Verificar import dos bindings**

Run:
```bash
python3 -c "import gi, cairo; gi.require_version('Gtk','3.0'); gi.require_version('AyatanaAppIndicator3','0.1'); from gi.repository import Gtk, AyatanaAppIndicator3; print('OK')"
```
Expected: imprime `OK`.

- [ ] **Step 3: Criar pacotes**

Create `claude_usage_bar/__init__.py`:
```python
"""claude-usage-bar — indicador de uso do plano Claude Code para GNOME."""
__version__ = "0.1.0"
```

Create `tests/__init__.py`:
```python
```
(arquivo vazio — marca `tests` como pacote)

- [ ] **Step 4: Commit**

```bash
cd /home/artur/pessoal/claude-usage-bar
git add claude_usage_bar/__init__.py tests/__init__.py
git commit -m "chore: esqueleto do pacote"
```

---

### Task 1: format.py — funções puras (TDD)

**Files:**
- Create: `claude_usage_bar/format.py`
- Test: `tests/test_format.py`

- [ ] **Step 1: Escrever o teste que falha**

Create `tests/test_format.py`:
```python
import unittest
from claude_usage_bar import format as fmt


class TestParsePercent(unittest.TestCase):
    def test_fraction(self):
        self.assertEqual(fmt.parse_percent("0.41"), 41.0)

    def test_percent(self):
        self.assertEqual(fmt.parse_percent("41"), 41.0)

    def test_decimal_percent(self):
        self.assertEqual(fmt.parse_percent("85.5"), 85.5)

    def test_one_is_fraction(self):
        self.assertEqual(fmt.parse_percent("1"), 100.0)

    def test_zero(self):
        self.assertEqual(fmt.parse_percent("0"), 0.0)

    def test_invalid(self):
        self.assertEqual(fmt.parse_percent(""), 0.0)
        self.assertEqual(fmt.parse_percent("abc"), 0.0)
        self.assertEqual(fmt.parse_percent(None), 0.0)


class TestResetText(unittest.TestCase):
    NOW = 1_000_000.0

    def test_none(self):
        self.assertEqual(fmt.reset_text(None, now=self.NOW), "")

    def test_past(self):
        self.assertEqual(fmt.reset_text(self.NOW - 10, now=self.NOW), "reset agora")

    def test_minutes(self):
        self.assertEqual(fmt.reset_text(self.NOW + 90, now=self.NOW), "reset 1m")

    def test_hours(self):
        self.assertEqual(fmt.reset_text(self.NOW + 5000, now=self.NOW), "reset 1h23m")

    def test_days(self):
        self.assertEqual(fmt.reset_text(self.NOW + 360000, now=self.NOW), "reset 4d4h")


class TestBarUnicode(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(fmt.bar_unicode(0), "░░░░░░░")

    def test_partial(self):
        self.assertEqual(fmt.bar_unicode(41), "███░░░░")

    def test_full(self):
        self.assertEqual(fmt.bar_unicode(100), "███████")


class TestLevel(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(fmt.level(79), "ok")

    def test_warn(self):
        self.assertEqual(fmt.level(80), "warn")

    def test_crit(self):
        self.assertEqual(fmt.level(95), "crit")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_format -v`
Expected: FAIL (`ModuleNotFoundError: claude_usage_bar.format`).

- [ ] **Step 3: Implementar**

Create `claude_usage_bar/format.py`:
```python
"""Funções puras de formatação/normalização. Sem I/O, sem rede — 100% testável."""
from __future__ import annotations

import time


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def parse_percent(raw: str | None) -> float:
    """Normaliza utilização p/ 0…100. Valores <= 1 são tratados como fração."""
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
    """Countdown legível a partir de epoch unix (s)."""
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
    """Barra estética: blocos cheios/vazios proporcionais ao %."""
    filled = round(clamp(pct) / 100 * cells)
    filled = max(0, min(cells, filled))
    return "█" * filled + "░" * (cells - filled)


def level(pct: float) -> str:
    """Severidade por limiar: 'ok' <80, 'warn' >=80, 'crit' >=95."""
    if pct >= 95:
        return "crit"
    if pct >= 80:
        return "warn"
    return "ok"
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_format -v`
Expected: PASS (todos os testes verdes).

- [ ] **Step 5: Commit**

```bash
git add claude_usage_bar/format.py tests/test_format.py
git commit -m "feat: funções puras de formatação (parse_percent, reset_text, bar_unicode, level)"
```

---

### Task 2: credentials.py — leitura read-only (TDD)

**Files:**
- Create: `claude_usage_bar/credentials.py`
- Test: `tests/test_credentials.py`

- [ ] **Step 1: Escrever o teste que falha**

Create `tests/test_credentials.py`:
```python
import json
import os
import tempfile
import unittest

from claude_usage_bar import credentials as cred


class TestRead(unittest.TestCase):
    def _write(self, obj):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f)
        self.addCleanup(os.remove, path)
        return path

    def test_valid(self):
        p = self._write({"claudeAiOauth": {"accessToken": "abc", "expiresAt": 1780592012214}})
        c = cred.read(p)
        self.assertEqual(c.access_token, "abc")
        self.assertEqual(c.expires_at_ms, 1780592012214)

    def test_missing_file(self):
        with self.assertRaises(cred.CredentialsError):
            cred.read("/nonexistent/path/x.json")

    def test_malformed_json(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            f.write("{not json")
        self.addCleanup(os.remove, path)
        with self.assertRaises(cred.CredentialsError):
            cred.read(path)

    def test_no_token(self):
        p = self._write({"claudeAiOauth": {"expiresAt": 123}})
        with self.assertRaises(cred.CredentialsError):
            cred.read(p)

    def test_no_oauth_key(self):
        p = self._write({"something": {}})
        with self.assertRaises(cred.CredentialsError):
            cred.read(p)


class TestExpiry(unittest.TestCase):
    def test_none_never_expires(self):
        self.assertFalse(cred.is_expired(None, now=1_000_000))

    def test_future(self):
        self.assertFalse(cred.is_expired(2_000_000_000_000, now=1_000_000))

    def test_past(self):
        self.assertTrue(cred.is_expired(1_000_000_000, now=2_000_000))

    def test_skew(self):
        exp_ms = (1_000_000 + 10) * 1000  # expira em 10s
        self.assertTrue(cred.is_expired(exp_ms, skew_s=30, now=1_000_000))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_credentials -v`
Expected: FAIL (`ModuleNotFoundError: claude_usage_bar.credentials`).

- [ ] **Step 3: Implementar**

Create `claude_usage_bar/credentials.py`:
```python
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_credentials -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add claude_usage_bar/credentials.py tests/test_credentials.py
git commit -m "feat: leitura read-only das credenciais do Claude + checagem de expiração"
```

---

### Task 3: claude_probe.py — parse_response (TDD) + fetch (rede)

**Files:**
- Create: `claude_usage_bar/claude_probe.py`
- Test: `tests/test_probe_parse.py`

- [ ] **Step 1: Escrever o teste que falha**

Create `tests/test_probe_parse.py`:
```python
import unittest

from claude_usage_bar.claude_probe import parse_response, ProbeError

H5U = "anthropic-ratelimit-unified-5h-utilization"
H5R = "anthropic-ratelimit-unified-5h-reset"
H7U = "anthropic-ratelimit-unified-7d-utilization"
H7R = "anthropic-ratelimit-unified-7d-reset"


class TestParseResponse(unittest.TestCase):
    def test_ok_fraction(self):
        u = parse_response(200, {H5U: "0.41", H7U: "0.12", H5R: "1700000000", H7R: "1700500000"})
        self.assertEqual(u.five_hour_pct, 41.0)
        self.assertEqual(u.seven_day_pct, 12.0)
        self.assertEqual(u.five_hour_reset_epoch, 1700000000.0)
        self.assertEqual(u.seven_day_reset_epoch, 1700500000.0)

    def test_ok_percent_case_insensitive(self):
        u = parse_response(200, {H5U.upper(): "41", H7U.upper(): "12"})
        self.assertEqual(u.five_hour_pct, 41.0)
        self.assertEqual(u.seven_day_pct, 12.0)
        self.assertIsNone(u.five_hour_reset_epoch)

    def test_429_still_parses(self):
        u = parse_response(429, {H5U: "0.99", H7U: "0.50"})
        self.assertEqual(u.five_hour_pct, 99.0)

    def test_401_unauthorized(self):
        with self.assertRaises(ProbeError) as ctx:
            parse_response(401, {})
        self.assertEqual(ctx.exception.kind, "unauthorized")

    def test_403_unauthorized(self):
        with self.assertRaises(ProbeError) as ctx:
            parse_response(403, {})
        self.assertEqual(ctx.exception.kind, "unauthorized")

    def test_400_no_headers_http(self):
        with self.assertRaises(ProbeError) as ctx:
            parse_response(400, {})
        self.assertEqual(ctx.exception.kind, "http")

    def test_200_no_headers(self):
        with self.assertRaises(ProbeError) as ctx:
            parse_response(200, {})
        self.assertEqual(ctx.exception.kind, "no_headers")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_probe_parse -v`
Expected: FAIL (`ModuleNotFoundError: claude_usage_bar.claude_probe`).

- [ ] **Step 3: Implementar**

Create `claude_usage_bar/claude_probe.py`:
```python
"""Probe da Messages API com o token OAuth do Claude Code → headers de rate-limit."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Mapping

from .credentials import Credentials
from .format import parse_percent

ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OAUTH_BETA = "oauth-2025-04-20"
USER_AGENT = "claude-code/2.1.5"
PROBE_MODEL = "claude-haiku-4-5-20251001"
TIMEOUT_S = 20

H5_UTIL = "anthropic-ratelimit-unified-5h-utilization"
H5_RESET = "anthropic-ratelimit-unified-5h-reset"
H7_UTIL = "anthropic-ratelimit-unified-7d-utilization"
H7_RESET = "anthropic-ratelimit-unified-7d-reset"


@dataclass
class Usage:
    five_hour_pct: float
    seven_day_pct: float
    five_hour_reset_epoch: float | None
    seven_day_reset_epoch: float | None


class ProbeError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


def _lower_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {str(k).lower(): v for k, v in headers.items()}


def _opt_float(raw) -> float | None:
    if raw is None:
        return None
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def parse_response(status: int, headers: Mapping[str, str]) -> Usage:
    """Pura: status + headers → Usage, ou levanta ProbeError. Sem rede."""
    if status in (401, 403):
        raise ProbeError("unauthorized", "token expirado — rode 'claude' uma vez")

    h = _lower_headers(headers)
    five = h.get(H5_UTIL)
    seven = h.get(H7_UTIL)
    if five is None or seven is None:
        if not (200 <= status <= 299):
            raise ProbeError("http", f"HTTP {status}")
        raise ProbeError("no_headers", "sem headers de rate-limit")

    return Usage(
        five_hour_pct=parse_percent(five),
        seven_day_pct=parse_percent(seven),
        five_hour_reset_epoch=_opt_float(h.get(H5_RESET)),
        seven_day_reset_epoch=_opt_float(h.get(H7_RESET)),
    )


def fetch(creds: Credentials) -> Usage:
    """Request mínimo (max_tokens:1); corpo ignorado, só os headers importam."""
    body = json.dumps({
        "model": PROBE_MODEL,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "."}],
    }).encode()

    req = urllib.request.Request(ENDPOINT, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {creds.access_token}")
    req.add_header("anthropic-version", ANTHROPIC_VERSION)
    req.add_header("anthropic-beta", OAUTH_BETA)
    req.add_header("content-type", "application/json")
    req.add_header("User-Agent", USER_AGENT)

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return parse_response(resp.status, dict(resp.headers.items()))
    except urllib.error.HTTPError as e:
        # headers de rate-limit vêm mesmo em 4xx → tenta parsear antes de falhar
        hdrs = dict(e.headers.items()) if e.headers else {}
        return parse_response(e.code, hdrs)
    except urllib.error.URLError as e:
        raise ProbeError("transport", f"rede: {e.reason}")
    except TimeoutError:
        raise ProbeError("transport", "timeout")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_probe_parse -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add claude_usage_bar/claude_probe.py tests/test_probe_parse.py
git commit -m "feat: probe do Claude (parse_response puro + fetch via urllib)"
```

---

### Task 4: model.py — estado + orquestração (TDD)

**Files:**
- Create: `claude_usage_bar/model.py`
- Test: `tests/test_model.py`

- [ ] **Step 1: Escrever o teste que falha**

Create `tests/test_model.py`:
```python
import unittest

from claude_usage_bar.model import UsageModel
from claude_usage_bar.credentials import Credentials, CredentialsError
from claude_usage_bar.claude_probe import Usage, ProbeError

FIXED_NOW = 1_000_000.0


def now():
    return FIXED_NOW


def good_creds():
    return Credentials(access_token="t", expires_at_ms=(FIXED_NOW + 3600) * 1000)


class TestModel(unittest.TestCase):
    def test_success(self):
        m = UsageModel()
        u = Usage(41, 12, None, None)
        m.run_refresh(read_creds=good_creds, prober=lambda c: u, now=now)
        self.assertIs(m.usage, u)
        self.assertIsNone(m.error)
        self.assertEqual(m.last_updated, FIXED_NOW)

    def test_credentials_error(self):
        m = UsageModel()

        def bad():
            raise CredentialsError("sem login")

        m.run_refresh(read_creds=bad, prober=lambda c: None, now=now)
        self.assertIsNone(m.usage)
        self.assertEqual(m.error, "sem login")

    def test_expired_token_short_circuits(self):
        m = UsageModel()
        expired = Credentials(access_token="t", expires_at_ms=(FIXED_NOW - 10) * 1000)
        called = {"probe": False}

        def prober(c):
            called["probe"] = True
            return Usage(0, 0, None, None)

        m.run_refresh(read_creds=lambda: expired, prober=prober, now=now)
        self.assertFalse(called["probe"])
        self.assertIn("expirado", m.error)

    def test_probe_error_keeps_message(self):
        m = UsageModel()

        def prober(c):
            raise ProbeError("transport", "timeout")

        m.run_refresh(read_creds=good_creds, prober=prober, now=now)
        self.assertEqual(m.error, "timeout")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_model -v`
Expected: FAIL (`ModuleNotFoundError: claude_usage_bar.model`).

- [ ] **Step 3: Implementar**

Create `claude_usage_bar/model.py`:
```python
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_model -v`
Expected: PASS.

- [ ] **Step 5: Rodar a suite inteira**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: PASS (todos os arquivos de teste).

- [ ] **Step 6: Commit**

```bash
git add claude_usage_bar/model.py tests/test_model.py
git commit -m "feat: UsageModel com orquestração de refresh testável"
```

---

### Task 5: icon.py — medidor Cairo (smoke test)

**Files:**
- Create: `claude_usage_bar/icon.py`
- Test: `tests/test_icon.py`

- [ ] **Step 1: Escrever o teste que falha**

Create `tests/test_icon.py`:
```python
import os
import tempfile
import unittest

from claude_usage_bar import icon


class TestIcon(unittest.TestCase):
    def _render(self, pct, state):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "g.png")
        icon.render_png(p, pct, state)
        self.addCleanup(lambda: (os.path.exists(p) and os.remove(p), os.rmdir(d)))
        return p

    def test_creates_valid_png(self):
        p = self._render(41, "ok")
        self.assertGreater(os.path.getsize(p), 0)
        with open(p, "rb") as f:
            self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")

    def test_idle(self):
        p = self._render(None, "idle")
        self.assertGreater(os.path.getsize(p), 0)

    def test_full_crit(self):
        p = self._render(100, "crit")
        self.assertGreater(os.path.getsize(p), 0)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m unittest tests.test_icon -v`
Expected: FAIL (`ModuleNotFoundError: claude_usage_bar.icon`).

- [ ] **Step 3: Implementar**

Create `claude_usage_bar/icon.py`:
```python
"""Desenha o ícone medidor (anel) com Cairo e grava PNG."""
from __future__ import annotations

import math

import cairo

# RGB por estado/limiar
COLORS = {
    "ok":   (0.30, 0.78, 0.31),   # verde
    "warn": (0.95, 0.61, 0.07),   # laranja
    "crit": (0.90, 0.22, 0.21),   # vermelho
    "idle": (0.55, 0.55, 0.55),   # cinza (carregando/erro)
}
SIZE = 22
RING = 4.0  # espessura do anel


def render_png(path: str, pct: float | None, state: str) -> None:
    """state em {'ok','warn','crit','idle'}. pct None ou state 'idle' → anel cinza vazio."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, SIZE, SIZE)
    ctx = cairo.Context(surface)
    cx = cy = SIZE / 2
    radius = SIZE / 2 - RING / 2 - 1

    # trilho de fundo
    ctx.set_line_width(RING)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source_rgba(0.5, 0.5, 0.5, 0.30)
    ctx.arc(cx, cy, radius, 0, 2 * math.pi)
    ctx.stroke()

    # arco preenchido (a partir do topo, sentido horário)
    if pct and pct > 0 and state != "idle":
        frac = max(0.0, min(1.0, pct / 100.0))
        r, g, b = COLORS.get(state, COLORS["ok"])
        ctx.set_source_rgb(r, g, b)
        start = -math.pi / 2
        end = start + 2 * math.pi * frac
        ctx.arc(cx, cy, radius, start, end)
        ctx.stroke()

    surface.write_to_png(path)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m unittest tests.test_icon -v`
Expected: PASS.

- [ ] **Step 5: Inspeção visual rápida (opcional mas recomendado)**

Run:
```bash
python3 -c "from claude_usage_bar import icon; icon.render_png('/tmp/g_ok.png', 41, 'ok'); icon.render_png('/tmp/g_crit.png', 97, 'crit'); print('/tmp/g_ok.png /tmp/g_crit.png')"
xdg-open /tmp/g_ok.png
```
Expected: abre um anel verde ~1/3 preenchido. Ajustar `SIZE`/`RING` se ilegível.

- [ ] **Step 6: Commit**

```bash
git add claude_usage_bar/icon.py tests/test_icon.py
git commit -m "feat: ícone medidor (anel Cairo) com cor por limiar"
```

---

### Task 6: indicator.py — AppIndicator + menu + timer (manual)

**Files:**
- Create: `claude_usage_bar/indicator.py`

- [ ] **Step 1: Implementar**

Create `claude_usage_bar/indicator.py`:
```python
"""AppIndicator (bandeja) + menu + timer. Camada GTK; orquestra model/icon."""
from __future__ import annotations

import os
import tempfile
import threading
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import Gtk, GLib, AyatanaAppIndicator3 as AppIndicator  # noqa: E402

from . import icon  # noqa: E402
from .format import bar_unicode, reset_text, level  # noqa: E402
from .model import UsageModel  # noqa: E402

APP_ID = "claude-usage-bar"
REFRESH_S = 300


class TrayApp:
    def __init__(self) -> None:
        self.model = UsageModel()
        self._icon_dir = tempfile.mkdtemp(prefix="claude-usage-bar-")
        self._icon_counter = 0

        self.indicator = AppIndicator.Indicator.new(
            APP_ID, "", AppIndicator.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_icon_theme_path(self._icon_dir)
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self._set_icon(None, "idle")
        self.indicator.set_menu(self._build_menu())

        self.refresh()
        GLib.timeout_add_seconds(REFRESH_S, self._on_timer)

    # ---- ícone ----
    def _set_icon(self, pct, state) -> None:
        self._icon_counter += 1
        name = f"gauge-{self._icon_counter}"
        path = os.path.join(self._icon_dir, name + ".png")
        icon.render_png(path, pct, state)
        self.indicator.set_icon_full(name, "Claude usage")

    def _worst(self):
        u = self.model.usage
        if not u:
            return None
        return max(u.five_hour_pct, u.seven_day_pct)

    def _update_icon(self) -> None:
        worst = self._worst()
        if worst is None:
            self._set_icon(None, "idle")
        else:
            self._set_icon(worst, level(worst))

    # ---- menu ----
    def _build_menu(self) -> Gtk.Menu:
        menu = Gtk.Menu()

        header = Gtk.MenuItem(label="Uso do plano")
        header.set_sensitive(False)
        menu.append(header)
        menu.append(Gtk.SeparatorMenuItem())

        u = self.model.usage
        if u:
            rows = [
                ("5h", u.five_hour_pct, u.five_hour_reset_epoch),
                ("7d", u.seven_day_pct, u.seven_day_reset_epoch),
            ]
            for lbl, pct, epoch in rows:
                txt = f"  {lbl}  ▕{bar_unicode(pct)}▏  {pct:.0f}%   {reset_text(epoch)}"
                item = Gtk.MenuItem(label=txt.rstrip())
                item.set_sensitive(False)
                menu.append(item)
        if self.model.error:
            err = Gtk.MenuItem(label=f"  ⚠ {self.model.error}")
            err.set_sensitive(False)
            menu.append(err)
        if not u and not self.model.error:
            loading = Gtk.MenuItem(label="  carregando…")
            loading.set_sensitive(False)
            menu.append(loading)

        menu.append(Gtk.SeparatorMenuItem())

        upd = self.model.last_updated
        when = time.strftime("%H:%M:%S", time.localtime(upd)) if upd else ""
        refresh_item = Gtk.MenuItem(label=f"↻ Atualizar agora        {when}".rstrip())
        refresh_item.connect("activate", lambda _w: self.refresh())
        menu.append(refresh_item)

        quit_item = Gtk.MenuItem(label="⏻ Sair")
        quit_item.connect("activate", lambda _w: Gtk.main_quit())
        menu.append(quit_item)

        menu.show_all()
        return menu

    def _rebuild_menu(self) -> None:
        self.indicator.set_menu(self._build_menu())

    # ---- refresh ----
    def _on_timer(self) -> bool:
        self.refresh()
        return True  # mantém o timer recorrente

    def refresh(self) -> None:
        self.model.is_loading = True
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self) -> None:
        self.model.run_refresh()
        GLib.idle_add(self._apply)

    def _apply(self) -> bool:
        self.model.is_loading = False
        self._update_icon()
        self._rebuild_menu()
        return False  # idle_add one-shot


def main() -> None:
    TrayApp()
    Gtk.main()
```

- [ ] **Step 2: Commit**

```bash
git add claude_usage_bar/indicator.py
git commit -m "feat: camada GTK (AppIndicator + menu + timer + refresh em thread)"
```

---

### Task 7: main.py — entrypoint e primeira execução real

**Files:**
- Create: `main.py`

- [ ] **Step 1: Implementar**

Create `main.py`:
```python
#!/usr/bin/env python3
"""Entrypoint do claude-usage-bar."""
from claude_usage_bar.indicator import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Rodar o app de verdade**

Run: `python3 main.py`
Expected: aparece um ícone (anel) na barra superior do GNOME. Após alguns
segundos o anel ganha cor (verde/laranja/vermelho conforme seu uso real). Clicar
abre o menu com `5h`/`7d`, %, barras unicode e countdown de reset.

- [ ] **Step 3: Validar interações**

- Clicar em "↻ Atualizar agora" → menu atualiza o horário.
- Confirmar que as % batem com seu uso atual.
- Clicar em "⏻ Sair" → ícone some, processo encerra.

Se o ícone não atualizar de cor entre ciclos (problema conhecido do
`set_icon_full`), aplicar Plano B: alternar entre dois nomes fixos
`gauge-a`/`gauge-b` no método `_set_icon`.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: entrypoint main.py"
```

---

### Task 8: install.sh, autostart.sh, README.md, LICENSE

**Files:**
- Create: `install.sh`, `autostart.sh`, `README.md`, `LICENSE`

- [ ] **Step 1: install.sh**

Create `install.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

APP="claude-usage-bar"
DEST="${HOME}/.local/share/${APP}"

echo "==> dependências de sistema (apt)"
sudo apt-get update -qq
sudo apt-get install -y python3-gi python3-gi-cairo python3-cairo \
  gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1

echo "==> copiando para ${DEST}"
mkdir -p "${DEST}"
rm -rf "${DEST}/claude_usage_bar"
cp -r claude_usage_bar main.py "${DEST}/"

echo "==> launcher .desktop"
APPS="${HOME}/.local/share/applications"
mkdir -p "${APPS}"
cat > "${APPS}/${APP}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Usage Bar
Comment=Indicador de uso do plano Claude Code
Exec=python3 ${DEST}/main.py
Icon=utilities-system-monitor
Terminal=false
Categories=Utility;
EOF

echo
echo "OK. Rode agora:      python3 ${DEST}/main.py"
echo "Autostart no login:  ./autostart.sh on"
```

- [ ] **Step 2: autostart.sh**

Create `autostart.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

APP="claude-usage-bar"
DEST="${HOME}/.local/share/${APP}"
AUTOSTART="${HOME}/.config/autostart/${APP}.desktop"

case "${1:-}" in
  on)
    mkdir -p "${HOME}/.config/autostart"
    cat > "${AUTOSTART}" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Usage Bar
Exec=python3 ${DEST}/main.py
X-GNOME-Autostart-enabled=true
Terminal=false
EOF
    echo "autostart ON  (${AUTOSTART})"
    ;;
  off)
    rm -f "${AUTOSTART}"
    echo "autostart OFF"
    ;;
  *)
    echo "uso: ./autostart.sh on|off"; exit 1 ;;
esac
```

- [ ] **Step 3: tornar executáveis**

Run: `chmod +x install.sh autostart.sh`

- [ ] **Step 4: README.md**

Create `README.md`:
```markdown
# Claude Usage Bar

Indicador de bandeja (system tray) para **Ubuntu/GNOME** que mostra o uso do seu
plano **Claude Code** em tempo real: janelas de **5h** e **7d** com countdown de
reset. Reusa o token que o Claude CLI já guarda — sem dashboard, sem login extra.

- Ícone medidor na barra superior que muda de cor: verde <80%, laranja ≥80%, vermelho ≥95%.
- Clique abre o menu com o detalhe: barras, % e horário de reset de cada janela.
- Atualiza a cada 5 minutos.

## Requisitos

- Ubuntu/GNOME com a extensão `ubuntu-appindicators` (padrão no Ubuntu).
- Python 3, GTK 3 e AppIndicator (instalados pelo `install.sh`).
- [Claude Code](https://claude.com/claude-code) instalado e logado.

## Instalação

```bash
git clone <url-do-repo> claude-usage-bar
cd claude-usage-bar
./install.sh
python3 ~/.local/share/claude-usage-bar/main.py
```

Iniciar junto com o login:

```bash
./autostart.sh on    # ligar
./autostart.sh off   # desligar
```

## Como funciona

| Item | Detalhe |
|---|---|
| Token | lido (read-only) de `~/.claude/.credentials.json` → `claudeAiOauth.accessToken` |
| Probe | `POST api.anthropic.com/v1/messages` (`max_tokens:1`) → lê headers `anthropic-ratelimit-unified-{5h,7d}-{utilization,reset}` |
| Custo | mínimo (1 request minúsculo a cada 5 min) |

O access token do Claude vive ~8h; quem o renova é o **Claude CLI**. Este app só
lê. Se ficar muito tempo sem usar o Claude Code, o ícone mostra `token expirado`
— basta rodar `claude` uma vez para o CLI renovar.

## Privacidade

O token é lido localmente e enviado só para a API da Anthropic. Nada é
armazenado, logado ou enviado a terceiros. O app **não** escreve no seu arquivo
de credenciais.

## Licença

[MIT](LICENSE)
```

- [ ] **Step 5: LICENSE**

Create `LICENSE` (MIT):
```
MIT License

Copyright (c) 2026 Artur Antunes

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 6: Commit**

```bash
git add install.sh autostart.sh README.md LICENSE
git commit -m "chore: install/autostart scripts, README e LICENSE"
```

---

### Task 9: Validação final real

- [ ] **Step 1: Suite completa verde**

Run: `python3 -m unittest discover -s tests -t . -v`
Expected: todos os testes PASS.

- [ ] **Step 2: Fluxo real ponta-a-ponta**

Run: `python3 main.py`
Confirmar com as credenciais reais desta máquina:
- ícone aparece e ganha cor coerente com o uso real;
- menu mostra `5h`/`7d` com % e reset plausíveis;
- "Atualizar agora" funciona; "Sair" encerra.

- [ ] **Step 3: Teste de expiração (opcional)**

Editar temporariamente um `expiresAt` no passado num arquivo de credencial de
teste e apontar `DEFAULT_PATH` — ou simplesmente aguardar a expiração natural —
e confirmar que o menu mostra `token expirado` e o ícone fica cinza. **Não
editar o arquivo real** `~/.claude/.credentials.json`.

---

## Self-Review (já validado)

**Cobertura da spec:**
- §4 stack → Task 0. §5 estrutura → Tasks 0–8. §6 fluxo → Tasks 4,6. §7 credenciais → Task 2. §8 probe → Task 3. §9 erros → Tasks 3,4. §10 funções puras → Task 1. §11 ícone → Task 5. §12 menu → Task 6. §13 threading → Task 6. §14 install/autostart → Task 8. §15 testes → Tasks 1–5,9. §16 riscos → Tasks 5,7 (planos B explícitos).
- Sem Codex em nenhuma task. App read-only (Task 2/4 nunca escrevem credencial).

**Consistência de tipos:** `Usage`, `Credentials`, `ProbeError(kind,message)`,
`CredentialsError`, `UsageModel.run_refresh(read_creds, prober, now)`,
`icon.render_png(path, pct, state)`, `format.{parse_percent,reset_text,bar_unicode,level}`
— nomes e assinaturas batem entre as tasks que os definem e as que os consomem.

**Placeholders:** nenhum TBD/TODO; todo passo de código mostra o código completo.
