#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE=${1:-/etc/postfix-entra-relay/relay.env}

if [[ ${EUID} -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi
[[ -r "$ENV_FILE" ]] || { echo "Missing $ENV_FILE" >&2; exit 1; }
# shellcheck disable=SC1090
source "$ENV_FILE"
: "${HVE_ADDRESS:?HVE_ADDRESS is required}"
: "${EXTERNAL_RELAY_ADDRESS:?EXTERNAL_RELAY_ADDRESS is required}"
: "${ARCHIVE_ADDRESS:?ARCHIVE_ADDRESS is required}"
: "${ACCEPTED_DOMAINS_FILE:?ACCEPTED_DOMAINS_FILE is required}"

"$ROOT/scripts/linux/generate-transport-map.sh" "$ACCEPTED_DOMAINS_FILE" /etc/postfix/transport_hve

if ! grep -q '^hvepipe[[:space:]]' /etc/postfix/master.cf; then
  cat "$ROOT/config/postfix/master.cf.snippet" >> /etc/postfix/master.cf
fi

postconf -e 'relayhost = [smtp.office365.com]:587'
postconf -e 'smtp_sasl_auth_enable = yes'
postconf -e 'smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd'
postconf -e 'smtp_sasl_security_options ='
postconf -e 'smtp_sasl_mechanism_filter = xoauth2'
postconf -e 'smtp_tls_security_level = encrypt'
postconf -e 'smtp_destination_concurrency_limit = 1'
postconf -e 'smtp_destination_rate_delay = 2s'
postconf -e 'transport_maps = hash:/etc/postfix/transport_hve, hash:/etc/postfix/transport'
postconf -e 'hvepipe_destination_recipient_limit = 1'
postconf -e "always_bcc = ${ARCHIVE_ADDRESS}"

postfix check
systemctl reload postfix
echo "POSTFIX_CONFIGURED"
