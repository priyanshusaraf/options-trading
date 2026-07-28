#!/usr/bin/env bash
#
# scripts/test_deploy_guards.sh — prove the deploy guards can go RED.
#
# A guard that has never been observed failing is a guard nobody has tested; an
# empty result and a passing result look identical from the outside. Every case
# here MUTATES a throwaway copy of deploy.sh (or its environment) into the exact
# state the guard exists to catch, and asserts both that it exits non-zero AND
# that the message names the right thing. A guard that fails with the wrong
# message is a guard that sends the operator to the wrong incident.
#
# Only the guards that run BEFORE the test suite are exercised end-to-end
# (Guards 0-2); the later ones would need a real venv run and a real host, so
# their red paths are asserted structurally.
#
#   bash scripts/test_deploy_guards.sh
#
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

pass_n=0; fail_n=0

# Run a mutated copy and assert: non-zero exit, and $2 appears in the output.
# --force-market-hours is passed by default so Guard 1 does not mask other cases;
# individual Guard-1 tests override the argument list.
expect_red() {
  local name="$1" needle="$2" script="$3"; shift 3
  local out rc
  out="$(cd "$(dirname "$SRC")/.." && bash "$script" "$@" 2>&1)"; rc=$?
  if [[ $rc -eq 0 ]]; then
    printf '\033[1;31mFAIL\033[0m %s — guard stayed GREEN (exit 0); it cannot detect this.\n' "$name"
    fail_n=$((fail_n + 1)); return
  fi
  if ! printf '%s' "$out" | grep -qF -- "$needle"; then
    printf '\033[1;31mFAIL\033[0m %s — went red (exit %s) but the message never says %s\n' \
      "$name" "$rc" "'$needle'"
    printf '%s\n' "$out" | tail -6 | sed 's/^/        /'
    fail_n=$((fail_n + 1)); return
  fi
  printf '\033[1;32mPASS\033[0m %s — red, and says %s\n' "$name" "'$needle'"
  pass_n=$((pass_n + 1))
}

mutant() {  # mutant <name> <sed-expr...>  -> prints path to the mutated copy
  local name="$1"; shift
  local dst="$TMP/$name.sh"
  cp "$SRC" "$dst"
  local e; for e in "$@"; do sed -i '' "$e" "$dst"; done
  printf '%s' "$dst"
}

# Guard 2 inspects REPO_ROOT, which deploy.sh derives from its OWN location
# (dirname/..). A mutant in a bare temp dir therefore trips the "not a git
# repository" check first and never reaches the status logic. So these cases get
# a real scratch repo, with the copy at <scratch>/scripts/deploy.sh.
git_mutant() {
  local name="$1"; shift
  local root="$TMP/repo-$name"
  mkdir -p "$root/scripts"
  git -C "$root" init -q 2>/dev/null
  git -C "$root" config user.email t@t; git -C "$root" config user.name t
  : > "$root/seed"; git -C "$root" add -A 2>/dev/null
  git -C "$root" commit -qm seed 2>/dev/null
  cp "$SRC" "$root/scripts/deploy.sh"
  local e; for e in "$@"; do sed -i '' "$e" "$root/scripts/deploy.sh"; done
  printf '%s' "$root/scripts/deploy.sh"
}

echo "=== Guard 0 — exclude list ==="

# .env dropped from EXCLUDES: the exact edit that caused two outages.
expect_red "G0 .env removed" "'.env' is NOT in EXCLUDES" \
  "$(mutant g0-env "/^  --exclude '\.env'$/d")" --force-market-hours

# frontend/dist dropped: --prune would then delete the whole SPA.
expect_red "G0 frontend/dist removed" "'frontend/dist' is NOT in EXCLUDES" \
  "$(mutant g0-dist "\|^  --exclude 'frontend/dist'|d")" --force-market-hours

# The dot-glob dropped: *.db-* does NOT cover .db.lock / .db.predeploy-*.
expect_red "G0 '*.db.*' removed" "'*.db.*' is NOT in EXCLUDES" \
  "$(mutant g0-dbdot "/^  --exclude '\*\.db\.\*'/d")" --force-market-hours

# An orphaned --exclude flag: rsync would take the next token as a source path.
# This is the malformation that made a real prune list come back empty.
expect_red "G0 odd element count" "ODD count" \
  "$(mutant g0-odd "/^EXCLUDES=(\$/a\\
  --exclude
")" --force-market-hours

# Misalignment without changing the count: a pattern where a flag belongs.
expect_red "G0 misaligned pair" "expected '--exclude'" \
  "$(mutant g0-align "/^EXCLUDES=(\$/a\\
  'stray-pattern'\\
  'another-stray'
")" --force-market-hours

# Empty pattern: rsync ignores it silently, so the target is unprotected.
expect_red "G0 empty pattern" "EMPTY pattern" \
  "$(mutant g0-empty "s|^  --exclude '\.env'\$|  --exclude ''|")" --force-market-hours

echo
echo "=== Guard 1 — market hours ==="

# The regression this pass is about: a `date` that yields an unparseable value
# used to make the arithmetic comparison error out, which reads as FALSE, which
# means the guard PASSES and the deploy lands mid-session.
expect_red "G1 unparseable date" "was never evaluated" \
  "$(mutant g1-garbage "s|ist_now=\"\$(TZ=Asia/Kolkata date '+%u %H%M')\"|ist_now=\"garbage\"|")"

expect_red "G1 date command fails" "could not read the current IST time" \
  "$(mutant g1-fail "s|ist_now=\"\$(TZ=Asia/Kolkata date '+%u %H%M')\"|ist_now=\"\$(false)\"|")"

# And it must still go red for the ordinary reason: it really is market hours.
expect_red "G1 inside session window" "market hours" \
  "$(mutant g1-live "s|ist_now=\"\$(TZ=Asia/Kolkata date '+%u %H%M')\"|ist_now=\"3 1000\"|")"

echo
echo "=== Guard 2 — dirty tree / git status ==="

# A git status that FAILS must not read as a clean tree. This is THE case: the
# old `[[ -n "$(git status --porcelain)" ]]` saw a broken status as empty output
# and shipped the on-disk tree under a SHA that does not describe it.
expect_red "G2 git status fails" "is not a clean tree" \
  "$(git_mutant g2-broken "s|git status --porcelain 2>|git nosuchsubcommand 2>|")" \
  --force-market-hours

# ...and it must still catch an ordinary dirty tree. Untracked counts: untracked
# files are rsynced too, so they ship code that is not in the SHA.
G2_DIRTY="$(git_mutant g2-dirty)"
: > "$(dirname "$G2_DIRTY")/../uncommitted.py"
expect_red "G2 dirty tree (untracked)" "working tree is dirty" \
  "$G2_DIRTY" --force-market-hours

echo
echo "=== Structural: later guards assert positively ==="

# These run after the suite/network, so assert the SHAPE of the check rather than
# executing it: each must have an affirmative branch, not just a failure branch.
structural() {
  local name="$1" needle="$2"
  if grep -qF -- "$needle" "$SRC"; then
    printf '\033[1;32mPASS\033[0m %s\n' "$name"; pass_n=$((pass_n + 1))
  else
    printf '\033[1;31mFAIL\033[0m %s — %s not found in deploy.sh\n' "$name" "'$needle'"
    fail_n=$((fail_n + 1))
  fi
}
structural "G3 asserts a positive pass count"   'no '"'"'N passed'"'"' summary line'
structural "G3 asserts a test-count floor"      'MIN_EXPECTED_TESTS'
structural "G3 asserts LEDGER OK affirmatively" "grep -qF 'LEDGER OK'"
structural "prune proves the tree was walked"   'incremental file list'
structural "prune rejects empty raw output"     'produced NO OUTPUT at all'
structural "remote checks split ssh 255"        'transport'
structural "health loop splits unreachable"     'ssh_failures'
structural "health loop requires a commit field" 'carries NO'

echo
printf 'passed %s, failed %s\n' "$pass_n" "$fail_n"
[[ $fail_n -eq 0 ]]
