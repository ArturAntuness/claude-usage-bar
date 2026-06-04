# Claude Usage Bar

Indicador de bandeja (system tray) para **Ubuntu/GNOME** que mostra o uso do seu
plano **Claude Code** em tempo real: janelas de **5h** e **7d** com countdown de
reset. Reusa o token que o Claude CLI já guarda — sem dashboard, sem login extra.

- Texto fixo na barra (`5h X%  7d Y%`) + anel medidor que muda de cor: verde <80%, laranja ≥80%, vermelho ≥95%.
- Clique abre o menu com o detalhe: barras, % e horário de reset de cada janela.
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

## Desenvolvimento

```bash
/usr/bin/python3 -m unittest discover -s tests -t . -v
```

## Licença

[MIT](LICENSE)
