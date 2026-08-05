#!/usr/bin/env bash
set -euo pipefail
MINUTES=${1:-15}
[[ $MINUTES =~ ^[0-9]+$ ]] || { echo "Minutes must be numeric" >&2; exit 2; }
SINCE="${MINUTES} minutes ago"

journalctl -u postfix --since "$SINCE" --no-pager 2>/dev/null \
  | grep -E 'status=(sent|deferred|bounced)|token_retry|config_error|tempfail' \
  | tail -n 200 || true

echo
echo "QUEUE_SUMMARY"
postqueue -p | tail -n 5
