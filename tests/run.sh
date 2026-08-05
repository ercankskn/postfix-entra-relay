#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m py_compile src/*.py dashboard/*.py
bash -n scripts/linux/*.sh tests/run.sh

python3 - <<'PY'
from pathlib import Path
import re
import sys
from urllib.parse import unquote

root = Path.cwd().resolve()
failures = []
pattern = re.compile(r'!?\[[^\]]*\]\(([^)]+)\)')
for document in root.rglob('*.md'):
    text = document.read_text(encoding='utf-8', errors='replace')
    for raw in pattern.findall(text):
        target = raw.strip().split()[0].strip('<>')
        if not target or target.startswith(('#', 'http://', 'https://', 'mailto:')):
            continue
        path_part = unquote(target.split('#', 1)[0])
        if not path_part:
            continue
        resolved = (document.parent / path_part).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            failures.append(f'{document}: link escapes repository: {target}')
            continue
        if not resolved.exists():
            failures.append(f'{document}: missing target: {target}')
if failures:
    print('\n'.join(failures), file=sys.stderr)
    raise SystemExit(1)
print('MARKDOWN_LINKS_OK')
PY

echo "REPOSITORY_TESTS_OK"
