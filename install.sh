#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Bitte als root ausführen: sudo ./install.sh" >&2
  exit 1
fi

INSTALL_DIR=/opt/prooffice-phonebook
SERVICE_USER=prooffice-phonebook
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v python3 >/dev/null || { echo "python3 fehlt" >&2; exit 1; }
python3 -m venv --help >/dev/null 2>&1 || { echo "python3-venv fehlt" >&2; exit 1; }

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 "$INSTALL_DIR" "$INSTALL_DIR/www" "$INSTALL_DIR/logs"
install -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0644 "$SCRIPT_DIR/app.py" "$INSTALL_DIR/app.py"
install -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0644 "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/requirements.txt"

if [ ! -f "$INSTALL_DIR/config.yml" ]; then
  install -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0644 "$SCRIPT_DIR/config.example.yml" "$INSTALL_DIR/config.yml"
fi

if [ ! -f "$INSTALL_DIR/.env" ]; then
  password="CHANGE_ME"
  token="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
  printf 'THREECX_PASSWORD=%s\nPHONEBOOK_ACCESS_TOKEN=%s\n' "$password" "$token" > "$INSTALL_DIR/.env"
  chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.env"
  chmod 0600 "$INSTALL_DIR/.env"
fi

python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

install -o root -g root -m 0644 "$SCRIPT_DIR/prooffice-phonebook.service" /etc/systemd/system/prooffice-phonebook.service
systemctl daemon-reload
systemctl enable --now prooffice-phonebook

echo "Installation abgeschlossen."
echo "Konfiguration: $INSTALL_DIR/config.yml"
echo "Zugangsdaten:  $INSTALL_DIR/.env"
echo "Portal:        http://SERVER:8095"
echo "Status:        systemctl status prooffice-phonebook"
