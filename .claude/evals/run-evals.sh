#!/usr/bin/env bash
# Strategy OS Claude-harness eval runner.
#
# Exercises the CONFIGURATION, not the codebase: each case is a realistic Strategy OS prompt
# whose correct handling depends on CLAUDE.md, .claude/rules/, and the skills/agents routing.
# A case passes when the response contains the markers the harness should have produced and
# none of the markers it should have suppressed.
#
# These are behavioural smoke tests, not proofs. A pass means the guidance reached the model;
# it does not mean the model would execute flawlessly. Read the transcripts.
#
# Usage:  .claude/evals/run-evals.sh [case-id-prefix ...]
# Output: .claude/evals/results/<id>.txt plus a summary table.

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
EVAL_DIR=".claude/evals"
OUT="$EVAL_DIR/results"
mkdir -p "$OUT"

cases=()
if [ $# -gt 0 ]; then
  for pre in "$@"; do
    for f in "$EVAL_DIR"/${pre}*.json; do [ -f "$f" ] && cases+=("$f"); done
  done
else
  for f in "$EVAL_DIR"/*.json; do [ -f "$f" ] && cases+=("$f"); done
fi

pass=0; fail=0
printf "%-26s %-6s %s\n" "CASE" "RESULT" "DETAIL"
printf "%-26s %-6s %s\n" "----" "------" "------"

for f in "${cases[@]}"; do
  id=$(jq -r '.id' "$f")
  prompt=$(jq -r '.prompt' "$f")
  resp_file="$OUT/$id.txt"

  # Read-only by tool restriction, exercising routing and reasoning without repo mutation.
  #
  # `env -u ANTHROPIC_API_KEY` is required, not cosmetic: an ANTHROPIC_API_KEY in the
  # environment takes precedence over the claude.ai login, and a stale one makes every
  # headless run fail with `401 API key is invalid` while interactive sessions keep working.
  # That is exactly the failure this runner hit on 2026-08-08. Unsetting it per-subprocess
  # keeps the user's shell untouched.
  # NOT --permission-mode plan: in headless mode a plan blocks on an approval that never
  # arrives, and the run hangs indefinitely (observed 2026-08-08, case 02 stalled at 0 bytes
  # for 15 minutes). Disallowing the mutating tools gets read-only behaviour without the stall.
  env -u ANTHROPIC_API_KEY claude -p "$prompt" \
    --disallowedTools Edit Write NotebookEdit \
    < /dev/null > "$resp_file" 2>&1
  body=$(tr '[:upper:]' '[:lower:]' < "$resp_file")

  missing=""; leaked=""
  while IFS= read -r m; do
    [ -z "$m" ] && continue
    # `m` is a |-alternation: the group passes if ANY alternative appears. Plain substring
    # matching produced false failures — case 01 said "doesn't warrant the full suite" and a
    # naive `expect_absent: full suite` caught the negation.
    if ! echo "$body" | grep -qE "$(echo "$m" | tr '[:upper:]' '[:lower:]')"; then missing="$missing [$m]"; fi
  done < <(jq -r '.expect_present[]?' "$f")
  while IFS= read -r m; do
    [ -z "$m" ] && continue
    if echo "$body" | grep -qE "$(echo "$m" | tr '[:upper:]' '[:lower:]')"; then leaked="$leaked [$m]"; fi
  done < <(jq -r '.expect_absent[]?' "$f")

  if [ -z "$missing" ] && [ -z "$leaked" ]; then
    pass=$((pass+1)); printf "%-26s %-6s %s\n" "$id" "PASS" "$(jq -r '.note' "$f")"
  else
    fail=$((fail+1))
    detail=""
    [ -n "$missing" ] && detail="missing:$missing"
    [ -n "$leaked" ] && detail="$detail leaked:$leaked"
    printf "%-26s %-6s %s\n" "$id" "FAIL" "$detail"
  fi
done

echo
echo "passed $pass / $((pass+fail))   transcripts in $OUT/"
[ "$fail" -eq 0 ]
