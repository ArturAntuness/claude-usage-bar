#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

APP="claude-usage-bar"
DEST="${HOME}/.local/share/${APP}"
PY="/usr/bin/python3"   # gi/cairo vivem no Python do sistema, não no pyenv

echo "==> dependências de sistema (apt)"
sudo apt-get update
sudo apt-get install -y python3-gi python3-gi-cairo python3-cairo \
  gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1

echo "==> copiando para ${DEST}"
mkdir -p "${DEST}"
rm -rf "${DEST}/claude_usage_bar"
cp -r claude_usage_bar main.py "${DEST}/"
find "${DEST}" -type d -name __pycache__ -exec rm -rf {} +   # não distribui bytecode

echo "==> launcher .desktop"
APPS="${HOME}/.local/share/applications"
mkdir -p "${APPS}"
cat > "${APPS}/${APP}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Usage Bar
Comment=Indicador de uso do plano Claude Code
Exec=${PY} ${DEST}/main.py
Icon=utilities-system-monitor
Terminal=false
Categories=Utility;
EOF

echo
echo "OK. Rode agora:      ${PY} ${DEST}/main.py"
echo "Autostart no login:  ./autostart.sh on"
