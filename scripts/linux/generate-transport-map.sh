#!/usr/bin/env bash
set -euo pipefail
INPUT=${1:-/etc/postfix-entra-relay/accepted-domains.txt}
OUTPUT=${2:-/etc/postfix/transport_hve}
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

[[ -r "$INPUT" ]] || { echo "Cannot read $INPUT" >&2; exit 1; }

awk '
  /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
  {
    domain=tolower($1)
    if (domain !~ /^[a-z0-9.-]+$/ || domain ~ /^\./ || domain ~ /\.$/ || domain ~ /\.\./) {
      printf "Invalid domain: %s\n", $1 > "/dev/stderr"; exit 2
    }
    print domain " hvepipe:"
  }
' "$INPUT" | sort -u > "$TMP"

install -o root -g root -m 0644 "$TMP" "$OUTPUT"
postmap "$OUTPUT"
echo "TRANSPORT_MAP_OK entries=$(wc -l < "$OUTPUT")"
