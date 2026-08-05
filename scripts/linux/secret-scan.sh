#!/usr/bin/env bash
set -euo pipefail
ROOT=${1:-.}
FAIL=0

scan_pattern() {
  local name=$1 pattern=$2
  local output
  output=$(grep -RInE --binary-files=without-match \
    --exclude-dir=.git --exclude-dir=.pytest_cache --exclude-dir=__pycache__ \
    --exclude='*.svg' --exclude='*.png' --exclude='*.jpg' --exclude='*.zip' \
    --exclude='*.gz' --exclude='*.bundle' \
    "$pattern" "$ROOT" 2>/dev/null || true)
  if [[ -n $output ]]; then
    echo "SECRET_SCAN_FAIL category=$name" >&2
    echo "$output" >&2
    FAIL=1
  fi
}

scan_pattern private_key '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'
scan_pattern jwt_token 'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}'
scan_pattern azure_secret "client_secret[\"' ]*[:=][\"' ][A-Za-z0-9~._-]{24,}"
scan_pattern refresh_token "refresh_token[\"' ]*[:=][\"' ][A-Za-z0-9._~-]{40,}"
scan_pattern sasl_trace 'auth=Bearer [A-Za-z0-9._~-]{20,}'

if [[ -n ${PUBLIC_DENYLIST_REGEX:-} ]]; then
  scan_pattern public_denylist "$PUBLIC_DENYLIST_REGEX"
fi

(( FAIL == 0 )) || exit 1
echo "PUBLIC_SECRET_SCAN_OK"
