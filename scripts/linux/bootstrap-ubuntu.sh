#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y postfix ca-certificates python3 python3-venv python3-pip jq curl rsyslog

getent group postfix-entra-hve >/dev/null || groupadd --system postfix-entra-hve
id postfix-entra-hve >/dev/null 2>&1 || useradd --system --gid postfix-entra-hve --home-dir /var/lib/postfix-entra-relay --shell /usr/sbin/nologin postfix-entra-hve

install -d -o root -g postfix-entra-hve -m 0750 /etc/postfix-entra-relay
install -d -o postfix-entra-hve -g postfix-entra-hve -m 0750 /var/lib/postfix-entra-relay
install -d -o root -g root -m 0755 /opt/postfix-entra-relay

echo "BOOTSTRAP_OK"
