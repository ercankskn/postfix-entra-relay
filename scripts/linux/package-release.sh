#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
OUT="$ROOT/release"
NAME="postfix-entra-relay-v${VERSION}"
rm -rf "$OUT"
mkdir -p "$OUT"

git -C "$ROOT" archive --format=tar.gz --prefix="$NAME/" -o "$OUT/$NAME.tar.gz" HEAD
git -C "$ROOT" archive --format=zip --prefix="$NAME/" -o "$OUT/$NAME.zip" HEAD
git -C "$ROOT" bundle create "$OUT/$NAME.bundle" --all
(
  cd "$OUT"
  sha256sum "$NAME.tar.gz" "$NAME.zip" "$NAME.bundle" > SHA256SUMS
)
echo "RELEASE_CREATED $OUT"
