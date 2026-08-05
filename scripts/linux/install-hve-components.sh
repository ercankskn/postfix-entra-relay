#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

install -o root -g postfix-entra-hve -m 0750 "$ROOT/src/postfix_entra_hve_submit.py" /usr/local/sbin/postfix-entra-hve-submit
install -o root -g root -m 0755 "$ROOT/src/postfix_entra_daily_origin_report.py" /usr/local/sbin/postfix-entra-daily-origin-report
install -o root -g root -m 0644 "$ROOT/config/systemd/postfix-entra-daily-origin-report.service" /etc/systemd/system/
install -o root -g root -m 0644 "$ROOT/config/systemd/postfix-entra-daily-origin-report.timer" /etc/systemd/system/

if [[ ! -e /etc/postfix-entra-relay/hve-oauth.json ]]; then
  install -o root -g postfix-entra-hve -m 0640 "$ROOT/config/hve/hve-oauth.json.example" /etc/postfix-entra-relay/hve-oauth.json
fi
if [[ ! -e /etc/postfix-entra-relay/report.json ]]; then
  install -o root -g root -m 0640 "$ROOT/config/hve/report.json.example" /etc/postfix-entra-relay/report.json
fi

systemctl daemon-reload
echo "HVE_COMPONENTS_INSTALLED"
