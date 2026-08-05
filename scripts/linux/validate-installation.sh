#!/usr/bin/env bash
set -euo pipefail

fail=0
check_file() {
  local path=$1
  if [[ -e $path ]]; then printf 'OK   %s\n' "$path"; else printf 'FAIL %s\n' "$path"; fail=1; fi
}

check_file /usr/local/sbin/postfix-entra-hve-submit
check_file /etc/postfix-entra-relay/hve-oauth.json
check_file /etc/postfix/transport_hve.db
check_file /etc/postfix/sasl_passwd.db

postfix check || fail=1
systemctl is-active --quiet postfix || fail=1
postconf -h transport_maps
postconf -h relayhost

if grep -RIEq '(^|[^A-Za-z])(eyJ[A-Za-z0-9_-]{20,}\.|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)' /etc/postfix-entra-relay 2>/dev/null; then
  echo "FAIL possible secret/token material found in text output" >&2
  fail=1
fi

(( fail == 0 )) || exit 1
echo "INSTALLATION_VALID"
