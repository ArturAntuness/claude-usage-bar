# Claude Usage Bar

Indicador de bandeja (system tray) para **Ubuntu/GNOME** que mostra o uso dos seus
planos **Claude Code** em tempo real — **uma ou várias contas ao mesmo tempo** — com
janelas de **5h** e **7d** e countdown de reset. Reusa os tokens que o Claude CLI já
guarda, sem dashboard nem login extra.

- **Multi-conta:** descobre automaticamente `~/.claude` e `~/.claude-*`. A barra
  mostra todas numa linha (`P 4/4  E 48/11  S 12/20`) e o menu tem uma **seção por conta**.
  Com **uma conta só**, mostra limpo: `5h 16%  7d 18%` (sem prefixo nem seção).
- **Anel medidor** que muda de cor pelo pior caso: verde <80%, laranja ≥80%, vermelho ≥95%.
- **Notificações** do GNOME quando uma conta cruza 80% / 95% (5h ou 7d).
- **Menu vivo:** abre e fica aberto, atualizando os valores e o countdown sem fechar.
- Atualiza a cada 5 minutos.

## Requisitos

- Ubuntu/GNOME com a extensão `ubuntu-appindicators` (padrão no Ubuntu).
- Python 3, GTK 3 e AppIndicator (instalados pelo `install.sh`).
- [Claude Code](https://claude.com/claude-code) instalado e logado.

> O app roda com o **Python do sistema** (`/usr/bin/python3`), onde vivem os
> bindings `gi`/`cairo`. Se você usa pyenv/virtualenv, isso não interfere.

## Instalação

```bash
git clone https://github.com/ArturAntuness/claude-usage-bar.git
cd claude-usage-bar
./install.sh
/usr/bin/python3 ~/.local/share/claude-usage-bar/main.py
```

Iniciar junto com o login:

```bash
./autostart.sh on    # ligar
./autostart.sh off   # desligar
```

## Como funciona

| Item | Detalhe |
|---|---|
| Contas | descobertas em `~/.claude` e `~/.claude-*` (que tenham `.credentials.json`); rótulo derivado do nome da pasta (`.claude`→Pessoal, `.claude-edge`→Edge…) |
| Token | lido (read-only) de cada `<conta>/.credentials.json` → `claudeAiOauth.accessToken` |
| Probe | `POST api.anthropic.com/v1/messages` (`max_tokens:1`) → lê headers `anthropic-ratelimit-unified-{5h,7d}-{utilization,reset}` |
| Custo | mínimo (1 request por conta a cada 5 min) |

O access token do Claude vive ~8h; quem o renova é o **Claude CLI**. Este app só
lê. Se ficar muito tempo sem usar o Claude Code, o ícone mostra `token expirado`
— basta rodar `claude` uma vez para o CLI renovar.

### Como ele atualiza o contador

1. Ao iniciar, faz a 1ª leitura. Depois um timer (`GLib.timeout_add_seconds`)
   dispara **a cada 5 minutos**.
2. Cada ciclo roda numa **thread separada** (não trava a interface): relê o token
   do arquivo, faz **1 requisição HTTPS** à Messages API e lê os headers
   `anthropic-ratelimit-unified-*`.
3. A Anthropic calcula o uso no servidor; o app só **lê** os números e redesenha
   o ícone + o texto da barra + o menu.
4. **Menu vivo:** ao abrir, o menu dispara um refresh e atualiza os valores e o
   countdown **no lugar**, sem fechar (os itens são atualizados, não recriados).
5. **Notificações:** a cada ciclo, se uma conta cruzou 80% ou 95% (5h/7d) **na
   subida**, dispara uma notificação do GNOME (não repete; rearma no reset).

> Os percentuais refletem o último ciclo (≤5 min atrás). O countdown de reset
> "anda" enquanto o menu está aberto.

## Consumo de recursos

Medido nesta máquina, com o app rodando:

| Recurso | Valor |
|---|---|
| Memória (PSS, privada real) | **~27 MB** |
| Memória (RSS) | ~56 MB |
| CPU | **~0%** parado entre ciclos (só o loop de eventos do GTK) |
| Rede | 1 request mínimo (`max_tokens:1`) a cada 5 min (~288/dia) |

A maior parte da RSS é de bibliotecas GTK **compartilhadas** com o resto do
desktop (por isso o PSS, que desconta o compartilhado, é bem menor). O custo de
cota da Anthropic por ciclo é uma fração ínfima.

## Segurança & Privacidade

- **Zero dependências de terceiros.** Apenas a biblioteca padrão do Python +
  GTK/Cairo/AppIndicator (pacotes de sistema do Ubuntu, assinados). Não há nada
  vindo do pip/PyPI — sem o risco clássico de uma lib comprometida na cadeia de
  dependências exfiltrar seu token.
- **O token nunca sai do lugar.** É lido (read-only) de
  `~/.claude/.credentials.json` (permissão `600`) e enviado **apenas** no header
  `Authorization`, por **HTTPS com verificação de certificado**, para o endpoint
  oficial `https://api.anthropic.com/v1/messages` (fixo no código). Nunca é
  impresso, logado nem gravado em arquivo.
- **Read-only.** O app não escreve no seu arquivo de credenciais — não tem como
  corromper seu login.
- **Exposição mínima.** Só o *access token* (~8h) é lido; o *refresh token*
  (longa duração) **nunca** é tocado.
- **Sem desserialização perigosa.** O corpo da resposta da API é ignorado (lemos
  só os headers de rate-limit). Sem `pickle`/`eval`.
- **Sem privilégio em runtime.** Roda como seu usuário, sem `sudo`. Apenas o
  `install.sh` usa `sudo`, e só para o `apt`.
- **Auditável.** São ~350 linhas em `claude_usage_bar/` — leia você mesmo.

> O token já vive no disco (no arquivo do Claude CLI, só legível por você). Este
> app não amplia essa exposição: quem já tem acesso ao seu usuário consegue ler o
> arquivo diretamente, com ou sem este app.

## Desenvolvimento

```bash
/usr/bin/python3 -m unittest discover -s tests -t . -v
```

## Licença

[MIT](LICENSE)
