#!/usr/bin/env bash
set -euo pipefail

APP="claude-usage-bar"
DEST="${HOME}/.local/share/${APP}"
AUTOSTART="${HOME}/.config/autostart/${APP}.desktop"
PY="/usr/bin/python3"

case "${1:-}" in
  on)
    mkdir -p "${HOME}/.config/autostart"
    cat > "${AUTOSTART}" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Usage Bar
Exec=${PY} ${DEST}/main.py
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
