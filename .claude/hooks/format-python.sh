#!/usr/bin/env bash
# PostToolUse hook (Edit|Write): format and lint-fix the Python file Claude just changed.
#
# - ruff format + ruff check --fix run on that single file (fast, no full-repo scan).
# - If ruff finds a problem it cannot fix, its report goes to stderr with exit code 2,
#   which Claude Code feeds back to Claude so it fixes the code itself.
# - Anything else (non-Python file, missing tools) exits 0 silently: a hook must never
#   block work because of its own environment.
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

if command -v uv >/dev/null 2>&1; then
  UV=(uv)
elif command -v py >/dev/null 2>&1; then
  UV=(py -m uv)  # Windows: uv installed per-user, not on PATH
else
  exit 0
fi

file=$("${UV[@]}" run --quiet python -c '
import json, sys
data = json.load(sys.stdin)
print((data.get("tool_input") or {}).get("file_path") or "")
' 2>/dev/null) || exit 0

case "$file" in
  *.py) ;;
  *) exit 0 ;;
esac
[ -f "$file" ] || exit 0

"${UV[@]}" run --quiet ruff format --quiet "$file" >/dev/null 2>&1

if ! report=$("${UV[@]}" run --quiet ruff check --fix --quiet "$file" 2>&1); then
  echo "ruff found issues it could not fix automatically in $file:" >&2
  echo "$report" >&2
  exit 2
fi
exit 0
