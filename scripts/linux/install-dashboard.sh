#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ ${EUID} -ne 0 ]]; then echo "Run as root." >&2; exit 1; fi
python3 -m venv /opt/postfix-entra-dashboard-venv
/opt/postfix-entra-dashboard-venv/bin/pip install --upgrade pip
/opt/postfix-entra-dashboard-venv/bin/pip install -r "$ROOT/dashboard/requirements.txt"
install -d -o root -g root -m 0755 /opt/postfix-entra-dashboard
install -o root -g root -m 0644 "$ROOT/dashboard/app.py" /opt/postfix-entra-dashboard/app.py
install -o root -g root -m 0755 "$ROOT/dashboard/collector.py" /opt/postfix-entra-dashboard/collector.py
install -o root -g root -m 0644 "$ROOT/config/systemd/postfix-entra-metrics.service" /etc/systemd/system/
install -o root -g root -m 0644 "$ROOT/config/systemd/postfix-entra-dashboard.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now postfix-entra-metrics.service postfix-entra-dashboard.service
echo "DASHBOARD_INSTALLED http://127.0.0.1:8765"
