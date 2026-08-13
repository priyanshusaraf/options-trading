#!/usr/bin/env bash
# Read-only behavioral smoke tests for the Strategy OS agent skills.
# Usage: .agents/evals/run-codex-evals.sh [case-id-prefix ...]
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"
eval_dir="$repo_root/.agents/evals"
out_dir="$repo_root/.agent/evals"
model="${CODEX_EVAL_MODEL:-gpt-5.6-terra}"
if [ -n "${CODEX_BIN:-}" ]; then
  codex_bin="$CODEX_BIN"
elif command -v codex >/dev/null 2>&1; then
  codex_bin=$(command -v codex)
elif [ -x /Applications/ChatGPT.app/Contents/Resources/codex ]; then
  codex_bin=/Applications/ChatGPT.app/Contents/Resources/codex
else
  echo "Codex CLI not found; set CODEX_BIN." >&2
  exit 2
fi
mkdir -p "$out_dir"

cases=()
if [ "$#" -gt 0 ]; then
  for prefix in "$@"; do
    for file in "$eval_dir"/"$prefix"*.json; do [ -f "$file" ] && cases+=("$file"); done
  done
else
  for file in "$eval_dir"/*.json; do [ -f "$file" ] && cases+=("$file"); done
fi

[ "${#cases[@]}" -gt 0 ] || { echo "No matching eval cases." >&2; exit 2; }
pass=0; fail=0
printf '%-34s %-6s %s\n' CASE RESULT DETAIL
for file in "${cases[@]}"; do
  id=$(jq -r '.id' "$file")
  prompt=$(jq -r '.prompt' "$file")
  skill=$(jq -r '.skill // empty' "$file")
  skill_instruction=""
  if [ -n "$skill" ]; then
    skill_instruction="Use the repository skill named $skill and its one directly relevant reference."
  fi
  transcript="$out_dir/$id.txt"
  answer="$out_dir/$id.answer.txt"
  : >"$answer"
  # Read-only sandbox plus an explicit instruction keeps an eval from changing the repository.
  "$codex_bin" exec --ephemeral --ignore-user-config --sandbox read-only -m "$model" \
    -c 'model_reasoning_effort="medium"' \
    -c 'features.apps=false' -c 'features.plugins=false' -c 'features.recommended_plugins=false' \
    -C "$eval_dir" -o "$answer" \
    "This is a bounded harness behavior eval. Follow the local eval instructions. $skill_instruction Answer only this hypothetical prompt: $prompt" \
    >"$transcript" 2>&1 || true
  body=$(tr '[:upper:]' '[:lower:]' <"$answer")
  missing=""; leaked=""
  while IFS= read -r pattern; do
    [ -z "$pattern" ] || grep -qE "$(printf '%s' "$pattern" | tr '[:upper:]' '[:lower:]')" <<<"$body" || missing="$missing [$pattern]"
  done < <(jq -r '.expect_present[]?' "$file")
  while IFS= read -r pattern; do
    [ -z "$pattern" ] || ! grep -qE "$(printf '%s' "$pattern" | tr '[:upper:]' '[:lower:]')" <<<"$body" || leaked="$leaked [$pattern]"
  done < <(jq -r '.expect_absent[]?' "$file")
  if [ ! -s "$answer" ]; then
    fail=$((fail + 1)); printf '%-34s %-6s %s\n' "$id" FAIL "Codex returned no final answer; see $transcript"
  elif [ -z "$missing$leaked" ]; then
    pass=$((pass + 1)); printf '%-34s %-6s %s\n' "$id" PASS "$(jq -r '.note' "$file")"
  else
    fail=$((fail + 1)); printf '%-34s %-6s missing:%s leaked:%s\n' "$id" FAIL "$missing" "$leaked"
  fi
done
printf 'passed %d / %d; transcripts: %s\n' "$pass" "$((pass + fail))" "$out_dir"
[ "$fail" -eq 0 ]
