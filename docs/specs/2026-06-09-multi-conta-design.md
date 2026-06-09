# claude-usage-bar — Multi-conta + redesign

- **Data:** 2026-06-09
- **Status:** Aprovado (aguardando revisão da spec)
- **Base:** evolução do app single-account (ver `2026-06-04-design.md`).

## 1. Objetivo

Mostrar o consumo de **múltiplas contas Claude ao mesmo tempo**, sem trocar de
conta/app. Caso real: 3 contas (Pessoal, Edge, Sulivam) usadas em paralelo. A
barra superior mostra um resumo das contas numa linha; o menu mostra cada conta
em sua própria seção com barras 5h/7d + reset.

## 2. Escopo

**Inclui:**
- Descoberta automática das contas (config dirs do Claude CLI).
- Barra: texto compacto `P 4/4  E 48/11  S 12/20` + ícone com cor do pior caso geral.
- Menu: uma seção por conta (PESSOAL/EDGE/SULIVAM) com 5h/7d (barra + % + reset).
- Refresh das N contas a cada 5 min.

**NÃO inclui (decisões explícitas):**
- Codex / outros providers. Só contas Claude.
- Escrita em credenciais / refresh ativo de token. **Passivo** (read-only) — conta
  ociosa >8h mostra `expirado` até o CLI dela renovar.
- Arquivo de config para renomear/ordenar/ocultar contas (evolução futura; por
  ora os rótulos são derivados do nome da pasta).
- Barras desenhadas na própria barra superior (a barra do GNOME é linha única;
  as barras vivem no menu).

## 3. Contexto verificado (esta máquina)

Aliases no `~/.zshrc`:
```
claudee='CLAUDE_CONFIG_DIR=$HOME/.claude-edge command claude'
claudes='CLAUDE_CONFIG_DIR=$HOME/.claude-sulivam command claude'
```
Config dirs com `.credentials.json`:

| Conta | Pasta | Rótulo derivado |
|---|---|---|
| Pessoal | `~/.claude` | Pessoal |
| Edge | `~/.claude-edge` | Edge |
| Sulivam | `~/.claude-sulivam` | Sulivam |

Cada conta é renovada pelo seu próprio CLI quando usada.

## 4. Descoberta de contas — `accounts.py` (novo)

```python
@dataclass
class Account:
    label: str
    credentials_path: str   # caminho absoluto do .credentials.json

def discover(home: str | None = None) -> list[Account]: ...
def derive_label(dir_basename: str) -> str: ...
```

Regras de `discover`:
- `home` default = `os.path.expanduser("~")`.
- Considera os diretórios `home/.claude` e `home/.claude-*` (glob no **raiz do
  home**, não recursivo) que contenham um arquivo `.credentials.json`.
- Para cada um, `Account(label=derive_label(basename), credentials_path=<dir>/.credentials.json)`.
- Ordena **Pessoal primeiro** (o `~/.claude`), depois alfabético por rótulo.
- Se nenhuma conta for encontrada, retorna lista vazia (a UI mostra "sem contas").

Regras de `derive_label(basename)`:

| basename | rótulo |
|---|---|
| `.claude` | `Pessoal` |
| `.claude-edge` | `Edge` |
| `.claude-sulivam` | `Sulivam` |
| `.claude-foo-bar` | `Foo-bar` (tira `.claude-`, capitaliza a 1ª letra) |

## 5. Camada de dados — refactor de `model.py`

Reaproveitados sem mudança: `credentials.read(path)` (já aceita path) e
`claude_probe.fetch(creds)`.

```python
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
    """Mesma lógica passiva de antes, por conta. Nunca levanta."""

@dataclass
class MultiModel:
    accounts: list[Account]
    results: list[AccountUsage] = field(default_factory=list)
    last_updated: float | None = None
    is_loading: bool = False

    def run_refresh(self, read=cred.read, prober=probe.fetch, now=time.time) -> None:
        self.results = [refresh_account(a, read, prober, now) for a in self.accounts]
        self.last_updated = now()
```

`refresh_account` (espelha o `run_refresh` atual, mas por conta e retornando
valor em vez de mutar estado global):
1. `c = read(account.credentials_path)`; se `CredentialsError` → `AccountUsage(account, None, str(e))`.
2. Se `cred.is_expired(c.expires_at_ms, now=now())` → `error="token expirado — rode o CLI desta conta"`.
3. Senão `prober(c)`; `ProbeError` → `error=e.message`.

## 6. UI — `indicator.py` + helpers em `format.py`

### 6.1 Funções puras (novas em `format.py`)
```python
def initial(label: str) -> str:        # "Pessoal" -> "P"; "" -> "?"
def format_bar(items) -> str:          # items: list[(label, pct5|None, pct7|None)]
```
`format_bar`: para cada item, `f"{initial(label)} {p5}/{p7}"` onde
`p = "%.0f" % v` se `v is not None` senão `"-"`. Junta com dois espaços.
Ex.: `[("Pessoal",4,4),("Edge",48,11),("Sulivam",12,20)]` → `"P 4/4  E 48/11  S 12/20"`.
Conta com erro/expirada (usage None) → `"E -/-"`.

### 6.2 Ícone
- Cor = pior caso **entre todas as contas**: `worst = max(max(u5,u7) for results com usage)`.
- `state = level(worst)`; se nenhuma conta tem usage → `"idle"` (cinza).
- `icon.render_png(path, worst, state)` — `icon.py` **não muda**.

### 6.3 Barra (label)
- `set_label(format_bar(items), LABEL_GUIDE)` onde `items` vem de `results`.
- `LABEL_GUIDE` = string generosa do tamanho de ~3 contas (ex.: `"P 99/99  E 99/99  S 99/99"`).

### 6.4 Menu (estilo popover da referência)
```
Uso do plano                         (cabeçalho, insensitive)
─────────────────────────
PESSOAL                              (insensitive)
  5h  ▕█░░░░░░▏   4%   reset 3h36m
  7d  ▕█░░░░░░▏   4%   reset 3d4h
─────────────────────────
EDGE
  5h  ▕███░░░░▏  48%   reset 3h15m
  7d  ▕█░░░░░░▏  11%   reset 2d13h
─────────────────────────
SULIVAM
  5h  ▕█░░░░░░▏  12%   reset 4h
  7d  ▕██░░░░░▏  20%   reset 5d2h
─────────────────────────
↻ Atualizar agora        (12:45:03)
⏻ Sair
```
- Conta com erro: no lugar das 2 linhas, uma linha `  ⚠ {error}`.
- Sem contas descobertas: uma linha `  nenhuma conta Claude encontrada`.

## 7. Refresh / threading

- A cada **300s** (`GLib.timeout_add_seconds`), 1 thread roda `MultiModel.run_refresh`,
  que percorre as contas **em sequência** (3 requests `max_tokens:1`, ~1s total,
  fora da main loop). Resultado volta via `GLib.idle_add` → atualiza ícone +
  label + menu.
- "Atualizar agora" dispara refresh fora de ciclo.
- (Paralelizar as contas em threads é possível, mas YAGNI: são 3 requests rápidos.)

## 8. Arquivos

| Arquivo | Ação |
|---|---|
| `claude_usage_bar/accounts.py` | **novo** — `Account`, `discover`, `derive_label` |
| `claude_usage_bar/model.py` | **refactor** — `AccountUsage`, `refresh_account`, `MultiModel` |
| `claude_usage_bar/format.py` | **+** `initial`, `format_bar` |
| `claude_usage_bar/indicator.py` | **refactor** — label/menu/ícone por N contas |
| `tests/test_accounts.py` | **novo** |
| `tests/test_model.py` | **refactor** — multi-conta |
| `tests/test_format.py` | **+** casos de `initial`/`format_bar` |
| `credentials.py`, `claude_probe.py`, `icon.py`, `main.py` | inalterados |

## 9. Testes

- **`test_accounts.py`** (HOME temporário com pastas fake):
  - `.claude` + `.claude-edge` + `.claude-sulivam` com `.credentials.json` → 3 contas, ordem Pessoal/Edge/Sulivam, rótulos certos.
  - pasta `.claude-x` **sem** `.credentials.json` → ignorada.
  - nenhuma pasta → lista vazia.
  - `derive_label`: tabela da seção 4.
- **`test_model.py`**: `refresh_account` (ok / `CredentialsError` / expirado / `ProbeError`) com fakes; `MultiModel.run_refresh` sobre 2-3 contas (mistura ok + erro) → `results` na ordem das contas, `last_updated` setado.
- **`test_format.py`**: `initial` (vários) + `format_bar` (todas com valor; uma com None → `-/-`; 1 conta só).
- **Validação real:** rodar contra as 3 contas reais; confirmar barra `P …  E …  S …`, menu com 3 seções e cores coerentes; simular 1 conta expirada (apontar um `.credentials.json` de teste com `expiresAt` no passado).

## 10. Riscos / pontos a validar

1. Largura do label com 3 contas na barra (pode ficar longo perto dos outros
   indicadores) — validar ao vivo; se preciso, encurtar (ex.: sem espaço duplo).
2. Altura do menu com 3 seções (≈15 itens) — ok em dropdown, validar.
3. Ordenação/derivação de rótulo para nomes de pasta inesperados (coberto por teste).
