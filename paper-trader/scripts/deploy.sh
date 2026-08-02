#!/usr/bin/env bash
#
# scripts/deploy.sh — the ONLY sanctioned path to production.
#
# Replaces ad-hoc `rsync -a` invocations, which have already caused two outages:
#   1. clobbered the VPS .env (dropped frontend-serve config -> every GET / 404
#      while health checks stayed green)
#   2. `rsync -a` as root stamped Mac uid 501 on directories, so the deploy user
#      could no longer create files
#
# Usage:
#   scripts/deploy.sh                       # normal deploy
#   scripts/deploy.sh --force-market-hours  # deploy inside the trading session
#   scripts/deploy.sh --dry-run             # show what would transfer, change nothing
#   scripts/deploy.sh --prune               # additionally delete remote-only files,
#                                           #   after showing the list and asking
#
# This script NEVER deletes on the remote unless --prune is passed. See the
# "why no --delete" note above the transfer section.
#
set -euo pipefail

# ---------------------------------------------------------------- config ----
VPS_HOST="${PT_VPS_HOST:-root@64.227.191.162}"
VPS_KEY="${PT_VPS_KEY:-$HOME/.ssh/paper-trader-vps}"
VPS_PATH="${PT_VPS_PATH:-/opt/paper-trader}"
SERVICE="${PT_SERVICE:-paper-trader}"
# Single base for every post-deploy probe, so health and GET / can never drift
# onto different ports. Both are curled from ON the VPS.
APP_BASE="${PT_APP_BASE:-http://127.0.0.1:8090}"

# scripts/ lives inside the deployed tree, so this resolves to paper-trader/ —
# which is what /opt/paper-trader mirrors. Do NOT move this script to the outer
# git root: REPO_ROOT would become the parent repo (stock-market-analyst/, data/,
# screenshots) and the real tree would land at $VPS_PATH/paper-trader/.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Anything here is NEVER pushed and NEVER pruned. Production owns these; they are
# not in git. Verified against a live `find /opt/paper-trader` on 2026-07-28 —
# if you add a remote-only artifact to the box, add it here in the same change.
EXCLUDES=(
  --exclude '.env'
  --exclude '.env.*'
  --exclude 'access_token.json'
  --exclude '*.db'
  --exclude '*.db-*'          # -wal, -shm  (HYPHEN suffixes only)
  --exclude '*.db.*'          # .db.lock, .db.predeploy-*  (DOT suffixes)
                              #   Both lines are required. `*.db-*` does NOT match
                              #   `paper_trader.db.lock` — verified with a real
                              #   openrsync --dry-run, not assumed. Without the
                              #   second line the live single-instance .db.lock is
                              #   in --prune's delete list; removing that path
                              #   while a backend holds the flock lets the next
                              #   boot create a fresh inode and take a second lock,
                              #   defeating the C7 guard.
  --exclude '*.log'
  --exclude '*.sql'           # ledger backups taken before risky operations
  --exclude 'backups'         # nightly DB backups, ~600MB, created by backup.sh
  --exclude 'backup.sh'       # the cron script that creates them — VPS-only
  --exclude 'frontend/dist'   # Gitignored, and BUILT ON THE MAC (see below) —
                              #   shipped by its own targeted rsync, never by the
                              #   main one. It stays excluded here precisely so
                              #   --prune cannot reach it: --delete honours
                              #   --exclude, so excluded == protected. Deleting it
                              #   is the .env outage's exact signature: GET / 404s
                              #   while /api/health stays 200.
  --exclude 'node_modules'
  --exclude '.venv'
  --exclude '__pycache__'
  --exclude '*.pyc'
  --exclude '.git'
  --exclude '.pytest_cache'
  --exclude '.playwright-mcp'
  --exclude 'vps-snapshots'
  --exclude '.DS_Store'
  --exclude 'VERSION'         # written per-host below, never synced from the Mac
)

FORCE_MARKET_HOURS=0
DRY_RUN=0
PRUNE=0
for arg in "$@"; do
  case "$arg" in
    --force-market-hours) FORCE_MARKET_HOURS=1 ;;
    --dry-run)            DRY_RUN=1 ;;
    --prune)              PRUNE=1 ;;
    --force)
      echo "--force is gone. Use --force-market-hours. There is deliberately no" >&2
      echo "flag to ship a dirty tree: a -dirty SHA in trades.build_sha is" >&2
      echo "untraceable by construction, which defeats the column." >&2
      exit 2 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mFAIL:\033[0m %s\n' "$*" >&2; exit 1; }

# ------------------------------------------------------- preflight guards ----

# Guard 0: the exclude list must be STRUCTURALLY sound and must contain every
# pattern an outage has already been traced to.
#
# Rewritten 2026-07-28 because the previous version had the failure mode this
# whole pass is about: it was a bare `grep -q ... || fail`, so "the pattern is
# absent" and "grep never inspected anything" were the same exit code and the
# same message, and a PASS printed nothing at all — identical to the guard having
# been deleted. Now: fixed-string matching (no BRE escaping to get wrong), the
# three outcomes kept apart, and a positive count printed on success.
#
# -F matters. The old patterns were hand-escaped BREs (`'\*\.db\.\*'`) matching
# array elements that contain no backslashes; one wrong escape and the guard
# silently matches nothing while looking correct.

exclude_count=${#EXCLUDES[@]}
[[ $exclude_count -gt 0 ]] \
  || fail "Guard 0: EXCLUDES is EMPTY. Nothing would be protected — .env, the live DB
      and frontend/dist would all be in scope. Refusing."
[[ $((exclude_count % 2)) -eq 0 ]] \
  || fail "Guard 0: EXCLUDES has $exclude_count elements — an ODD count means some
      '--exclude' has lost its pattern (or a pattern its flag). rsync would take the
      orphan as a POSITIONAL argument, which is exactly what made it skip deletion
      and print an empty prune list. Refusing."

# Pairwise alignment: even index must be the literal --exclude, odd index a
# non-empty pattern. Checked positionally rather than by "is --exclude present
# somewhere", which an entirely malformed array also satisfies.
for ((i = 0; i < exclude_count; i += 2)); do
  [[ "${EXCLUDES[i]}" == "--exclude" ]] \
    || fail "Guard 0: EXCLUDES[$i] is '${EXCLUDES[i]}', expected '--exclude' — the list
      is misaligned from this point on and every pattern after it is off by one. Refusing."
  [[ -n "${EXCLUDES[i + 1]}" ]] \
    || fail "Guard 0: EXCLUDES[$((i + 1))] is an EMPTY pattern — rsync ignores it
      silently, so the thing it was meant to protect is unprotected. Refusing."
done

# Every one of these has a specific outage or near-miss behind it.
REQUIRED_EXCLUDES=(
  '.env'              # clobbered production config twice
  '.env.*'
  'access_token.json' # the live Kite session
  '*.db'              # the real ledger
  '*.db-*'            # -wal / -shm   (HYPHEN suffixes)
  '*.db.*'            # .db.lock / .db.predeploy-*  (DOT suffixes — *.db-* misses these)
  'backups'
  'frontend/dist'     # excluded == protected from --prune; deleting it 404s the SPA
)
verified=0
for pat in "${REQUIRED_EXCLUDES[@]}"; do
  set +e
  printf '%s\n' "${EXCLUDES[@]}" | grep -qxF -- "$pat"
  rc=$?
  set -e
  case $rc in
    0) verified=$((verified + 1)) ;;
    1) fail "Guard 0: '$pat' is NOT in EXCLUDES. This pattern is here because its
      absence has already broken production. Refusing." ;;
    *) fail "Guard 0: grep exited $rc while inspecting EXCLUDES for '$pat'. The list was
      NOT inspected — this is a BROKEN CHECK, not a clean result. Refusing." ;;
  esac
done
[[ $verified -eq ${#REQUIRED_EXCLUDES[@]} ]] \
  || fail "Guard 0: verified only $verified of ${#REQUIRED_EXCLUDES[@]} required excludes.
      The loop above did not run to completion. Refusing."
log "Guard 0 OK: $exclude_count exclude tokens, $((exclude_count / 2)) patterns, all $verified required present"

# Guard 1: never deploy into a live session by accident.
# NSE/BSE cash + F&O trade 09:15-15:30 IST, Mon-Fri; buffered to 09:00-15:45.
if [[ $FORCE_MARKET_HOURS -eq 0 ]]; then
  ist_now="$(TZ=Asia/Kolkata date '+%u %H%M')" \
    || fail "Guard 1: could not read the current IST time. The market-hours check did not
      run — refusing to deploy blind into a possibly-live session."

  dow="${ist_now%% *}"; hhmm="${ist_now##* }"

  # Assert the PARSE before trusting the comparison. Previously an unparsed value
  # flowed straight into `[[ "10#$hhmm" -ge 900 ]]`, where bash raises an
  # arithmetic error and the condition evaluates FALSE — so a guard that broke was
  # a guard that PASSED, and the deploy went into the middle of a trading session.
  # Failing to look and looking-and-finding-nothing now take different paths.
  [[ "$dow" =~ ^[1-7]$ ]] \
    || fail "Guard 1: day-of-week parsed as '$dow' from '$ist_now' — expected a single
      digit 1-7. The market-hours window was never evaluated. Refusing."
  [[ "$hhmm" =~ ^[0-9]{4}$ ]] \
    || fail "Guard 1: time-of-day parsed as '$hhmm' from '$ist_now' — expected HHMM. The
      market-hours window was never evaluated. Refusing."

  if [[ "$dow" -le 5 ]] && [[ "10#$hhmm" -ge 900 ]] && [[ "10#$hhmm" -le 1545 ]]; then
    fail "market hours (IST $hhmm, day $dow). Deploy in a closed window, or pass --force-market-hours."
  fi
  log "Guard 1 OK: IST $hhmm day $dow — outside the 0900-1545 Mon-Fri session window"
else
  log "Guard 1 SKIPPED by --force-market-hours (IST $(TZ=Asia/Kolkata date '+%u %H%M')) — deploying into a possibly-live session"
fi

# Guard 2: know exactly what is shipping. A dirty tree is refused outright —
# there is no override. The whole point of stamping build_sha onto every trade is
# that the SHA can be checked out and diffed later; "abc1234-dirty" cannot.
cd "$REPO_ROOT"
command -v git >/dev/null || fail "git not found"
git rev-parse --git-dir >/dev/null 2>&1 \
  || fail "Guard 2: $REPO_ROOT is not a git repository. Nothing here can be identified,
      so trades.build_sha would be meaningless. Refusing."
SHA="$(git rev-parse --short HEAD)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[[ -n "$SHA" ]] || fail "Guard 2: git rev-parse returned an EMPTY short SHA. Refusing."

# --porcelain, not diff-index: untracked files are rsynced too, so an untracked
# .py ships code that is not in $SHA — the same untraceability, one step sideways.
# (Gitignored files, incl. backend/VERSION, do not appear here.)
#
# The exit code is captured SEPARATELY from the output. The previous form,
# `[[ -n "$(git status --porcelain)" ]]`, read a git status that FAILED — index.lock
# held by another process, a corrupt object, an unreadable worktree — as empty
# output, i.e. as a CLEAN TREE, and shipped whatever happened to be on disk stamped
# with a SHA that does not describe it. "No changes" and "could not look for
# changes" now print different things and take different paths.
set +e
porcelain="$(git status --porcelain 2>/tmp/pt-deploy-gitstatus.err)"
git_rc=$?
set -e
if [[ $git_rc -ne 0 ]]; then
  head -5 /tmp/pt-deploy-gitstatus.err >&2
  fail "Guard 2: 'git status --porcelain' exited $git_rc — the working tree was NOT
      inspected. An empty result from a failed status is not a clean tree; it is no
      information at all. Fix the repo state and re-run. Refusing."
fi

if [[ -n "$porcelain" ]]; then
  git status --short >&2
  fail "working tree is dirty (modified or untracked). Commit — or gitignore — before
      deploying. Uncommitted code cannot be identified from trades.build_sha, and
      this ledger is the record of real money."
fi
log "Guard 2 OK: git status inspected and clean — shipping $BRANCH@$SHA"

# Guard 3: tests must be green before anything touches production. Both suites:
# pytest.ini sets testpaths=tests, so research_tests/ needs naming explicitly.
# Both suites are named explicitly: pytest.ini sets testpaths=tests, so a bare
# pytest silently skips research_tests/ entirely.
MIN_EXPECTED_TESTS="${PT_MIN_TESTS:-1000}"   # 933 + 167 collected as of 2026-07-28

log "running backend suite (tests + research_tests)"
( cd "$REPO_ROOT/backend" && .venv/bin/python -m pytest tests research_tests --tb=short ) \
  > /tmp/pt-deploy-tests.log 2>&1 \
  || { tail -40 /tmp/pt-deploy-tests.log; fail "tests failed — see /tmp/pt-deploy-tests.log"; }

# Exit 0 is necessary, not sufficient. A run that collected almost nothing also
# exits 0: a conftest that errors out during collection, a testpaths edit, a
# rename that orphans a directory. "Nothing failed" and "nothing ran" are the same
# exit code, so assert the PASS COUNT positively.
passed="$(grep -oE '[0-9]+ passed' /tmp/pt-deploy-tests.log | tail -1 | grep -oE '^[0-9]+' || true)"
if [[ -z "$passed" ]]; then
  tail -20 /tmp/pt-deploy-tests.log >&2
  fail "Guard 3: pytest exited 0 but no 'N passed' summary line is in the log, so it is
      not established that a single test ran. Note pytest.ini already sets addopts=-q —
      adding another -q makes it -qq, which SUPPRESSES the summary line entirely.
      Refusing."
fi
[[ "$passed" -ge "$MIN_EXPECTED_TESTS" ]] \
  || fail "Guard 3: only $passed tests passed; expected at least $MIN_EXPECTED_TESTS.
      A collapse in the collected count means most of the app stopped being covered
      while the run still went green. Refusing. (Override: PT_MIN_TESTS=<n>.)"
log "Guard 3 OK: $passed tests passed across both suites (floor $MIN_EXPECTED_TESTS)"

log "running ledger reconciliation"
( cd "$REPO_ROOT/backend" && .venv/bin/python scripts/dryrun.py 700 ) \
  > /tmp/pt-deploy-dryrun.log 2>&1 \
  || { tail -40 /tmp/pt-deploy-dryrun.log; fail "dryrun/ledger invariant failed"; }

# Same shape: require the affirmative marker, not merely the absence of a failure.
grep -qF 'LEDGER OK' /tmp/pt-deploy-dryrun.log \
  || { tail -20 /tmp/pt-deploy-dryrun.log >&2
       fail "Guard 3: dryrun.py exited 0 but never printed 'LEDGER OK'. The paisa-exact
      reconciliation is the one invariant this ledger cannot ship without, and it was
      not confirmed. Refusing."; }
log "Guard 3 OK: ledger reconciled (LEDGER OK present in the dryrun output)"

# Guard 4: build the SPA HERE, on the Mac. It used to be built on the VPS, which
# is a 1GB droplet that has already OOM'd twice with the engine running — a Vite
# build there competes for memory with a process holding real positions and can
# take the engine down. Local build, then ship the artifact.
#
# frontend/dist is gitignored, so this cannot dirty the tree checked by Guard 2
# (which has already run, above).
if [[ $DRY_RUN -eq 1 ]]; then
  log "dry run: SKIPPING frontend build (it writes to frontend/dist, and a dry run changes nothing)"
else
  command -v npm >/dev/null || fail "npm not found — the SPA is built on the Mac now, not the VPS"
  [[ -d "$REPO_ROOT/frontend/node_modules" ]] \
    || fail "frontend/node_modules missing — run (cd frontend && npm install) first"

  log "building frontend on this machine (NOT on the 1GB droplet)"
  ( cd "$REPO_ROOT/frontend" && npm run build ) > /tmp/pt-deploy-build.log 2>&1 \
    || { tail -40 /tmp/pt-deploy-build.log; fail "frontend build failed — see /tmp/pt-deploy-build.log"; }

  # Refuse to ship an empty or half-written dist. The targeted rsync below would
  # otherwise happily overwrite a working remote SPA with nothing, which is the
  # 404-with-green-health failure mode this script exists to prevent.
  [[ -s "$REPO_ROOT/frontend/dist/index.html" ]] \
    || fail "frontend build produced no dist/index.html — refusing to ship an empty SPA"
  log "frontend built: $(find "$REPO_ROOT/frontend/dist" -type f | wc -l | tr -d ' ') files"
fi

# ------------------------------------------------------------- transfer -----
# NOTE: macOS ships openrsync ("rsync version 2.6.9 compatible"). Do not add
# modern flags (--info=progress2, --chmod, ...) and do not switch to -a: this
# rsync rejects long options when combined with -a.
# -rlptD instead of -a: deliberately drops -o/-g so running as root does not
# stamp local uid 501 onto remote directories.
#
# Why no --delete by default: /opt/paper-trader legitimately holds files that are
# not in git — the nightly backups/, backup.sh, VPS-built frontend/dist, ledger
# .sql dumps, the live .db.lock. VPS state also drifts during incident recovery.
# A one-time "first run" gate would protect run 1 and silently arm run 40, so
# deletion is opt-in per-invocation via --prune, which shows its work first.
RSYNC_FLAGS=(-rlptD --omit-dir-times --no-owner --no-group -v)
[[ $DRY_RUN -eq 1 ]] && RSYNC_FLAGS+=(--dry-run)

# Stamp the build into backend/, where the app reads it with no path traversal.
# Written after the guards (so a failed run leaves no misleading VERSION) and
# excluded from the sync (so it is generated per-host, not copied).
write_version() {
  cat > "$REPO_ROOT/backend/VERSION" <<EOF
commit=$SHA
branch=$BRANCH
deployed_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
deployed_by=$(whoami)@$(hostname -s)
EOF
}

# ------------------------------------------------------ rollback capture ----
# Read the OUTGOING build off the box and keep it, before anything overwrites it.
#
# The VPS has no git and backend/VERSION is written per-host, so the moment the
# new VERSION lands the identity of what was running is gone — leaving only an
# investigation. Captured here so a bad deploy is answered with:
#     git checkout <sha> && scripts/deploy.sh
#
# Stored OUTSIDE $REPO_ROOT on purpose: anything under it would be rsynced to
# production and would trip the dirty-tree guard on the next run.
DEPLOY_HISTORY="${PT_DEPLOY_HISTORY:-$HOME/.paper-trader/deploy-history}"
ROLLBACK_SHA=""

capture_rollback_point() {
  local remote
  # `|| echo __ABSENT__` keeps a missing file from looking like a failed ssh —
  # the two need different responses, and only one of them is normal.
  if ! remote="$(ssh -i "$VPS_KEY" -o StrictHostKeyChecking=accept-new "$VPS_HOST" \
        "cat $VPS_PATH/backend/VERSION 2>/dev/null || echo __ABSENT__" 2>/dev/null)"; then
    fail "cannot read the current build from $VPS_HOST — refusing to deploy without
      capturing a rollback point. Check the host, the key, and the network."
  fi

  if [[ "$remote" == "__ABSENT__" || -z "$remote" ]]; then
    printf '\033[1;33m==> no VERSION on the remote\033[0m — first deploy through this script,\n'
    printf '    or the box predates build stamping. NO ROLLBACK TARGET is recoverable\n'
    printf '    for the build being replaced. Every deploy after this one will have one.\n'
    return 0
  fi

  ROLLBACK_SHA="$(printf '%s\n' "$remote" | sed -n 's/^commit=//p' | head -1)"

  echo
  printf '\033[1;36m==> ROLLBACK POINT — the build being replaced\033[0m\n'
  printf '%s\n' "$remote" | sed 's/^/    /'
  echo

  if [[ $DRY_RUN -eq 1 ]]; then
    log "dry run: not writing to $DEPLOY_HISTORY"
  else
    mkdir -p "$DEPLOY_HISTORY"
    # Append-only log, plus a fixed filename for "the one you want right now".
    printf '%s\n' "$remote" > "$DEPLOY_HISTORY/$(date -u '+%Y%m%dT%H%M%SZ')-replaced-by-$SHA.VERSION"
    printf '%s\n' "$remote" > "$DEPLOY_HISTORY/previous-VERSION"
  fi

  if [[ -n "$ROLLBACK_SHA" ]]; then
    if git cat-file -e "${ROLLBACK_SHA}^{commit}" 2>/dev/null; then
      printf '    To roll back:  \033[1mgit checkout %s && scripts/deploy.sh\033[0m\n\n' "$ROLLBACK_SHA"
    else
      # Worth saying out loud: the SHA is captured but not reachable from here,
      # so `git checkout` will fail until the branch holding it is fetched.
      printf '\033[1;33m    WARNING: %s is not in this repo\033[0m — fetch the branch that\n' "$ROLLBACK_SHA"
      printf '    contains it before relying on this as a rollback target.\n\n'
    fi
  else
    printf '\033[1;33m    WARNING: remote VERSION has no commit= line\033[0m — no rollback SHA.\n\n'
  fi
}

capture_rollback_point

if [[ $PRUNE -eq 1 ]]; then
  log "PRUNE: computing what would be DELETED on the remote"
  # --delete respects --exclude (excluded files are protected, not removed), so
  # this lists only genuinely untracked-and-unprotected remote paths.
  #
  # The raw output is kept and checked BEFORE grepping. On any IO error rsync
  # prints "IO error encountered -- skipping file deletion" and computes no
  # deletions at all — which greps to an empty list and reads as "nothing to
  # prune", i.e. a failed computation is indistinguishable from a clean one.
  # Observed for real: a malformed exclude array made rsync treat a pattern as a
  # positional argument, and the empty list looked like reassurance.
  prune_raw="$(rsync "${RSYNC_FLAGS[@]}" --delete --dry-run "${EXCLUDES[@]}" \
    -e "ssh -i $VPS_KEY -o StrictHostKeyChecking=accept-new" \
    "$REPO_ROOT/" "$VPS_HOST:$VPS_PATH/" 2>&1)" || {
      printf '%s\n' "$prune_raw" | head -5 >&2
      fail "prune computation failed — refusing to guess. Nothing was changed."; }

  if printf '%s\n' "$prune_raw" | grep -q 'IO error'; then
    printf '%s\n' "$prune_raw" | grep -iE '^rsync.*error' | head -5 >&2
    fail "rsync hit an IO error and SKIPPED deletion — an empty prune list here would
      be meaningless, not safe. Fix the error and re-run."
  fi

  # Positive proof that rsync actually WALKED the remote tree. Exit 0 with no IO
  # error still covers the case where rsync produced nothing usable at all (a
  # misparsed argument, an empty source, a silently truncated run) — and that
  # greps to an empty deletion list, which reads as "nothing to prune".
  # An enumeration that happened always prints a file list and a summary.
  [[ -n "$prune_raw" ]] \
    || fail "prune computation produced NO OUTPUT at all. rsync did not enumerate the
      remote tree, so the empty deletion list below it means nothing. Refusing."
  printf '%s\n' "$prune_raw" | grep -qE '^(sending|receiving) incremental file list' \
    || { printf '%s\n' "$prune_raw" | head -10 >&2
         fail "prune computation output has no 'incremental file list' header, so rsync
      never started a real transfer walk. An empty deletion list from a walk that did
      not happen is not 'nothing to prune'. Refusing."; }

  prune_list="$(printf '%s\n' "$prune_raw" | grep '^deleting ' || true)"

  if [[ -z "$prune_list" ]]; then
    log "prune: remote tree enumerated ($(printf '%s\n' "$prune_raw" | wc -l | tr -d ' ') lines), 0 deletable paths — proceeding as a normal deploy"
    PRUNE=0
  else
    echo
    printf '\033[1;31mThese remote files will be PERMANENTLY DELETED:\033[0m\n'
    echo "$prune_list" | sed 's/^deleting /  - /'
    echo
    printf 'Count: %s\n\n' "$(echo "$prune_list" | wc -l | tr -d ' ')"
    if [[ $DRY_RUN -eq 1 ]]; then
      # `--prune --dry-run` exists to be READ before --prune is ever run for real.
      # No prompt: a confirmation here would be answering a question that changes
      # nothing, and training yourself to type 'delete' at this screen is precisely
      # the habit that makes the real prompt dangerous.
      log "dry run: the list above is what --prune WOULD delete. Nothing was changed."
    else
      read -r -p "Type 'delete' to confirm, anything else to abort: " confirm
      [[ "$confirm" == "delete" ]] || fail "prune aborted — nothing was changed"
      RSYNC_FLAGS+=(--delete)
    fi
  fi
fi

# Not on a dry run: --dry-run promises to change nothing, and that has to include
# the local tree. VERSION is excluded from the sync below and placed explicitly
# afterwards, so a dry run has no use for it anyway.
[[ $DRY_RUN -eq 0 ]] && write_version

log "syncing $BRANCH@$SHA -> $VPS_HOST:$VPS_PATH"
rsync "${RSYNC_FLAGS[@]}" "${EXCLUDES[@]}" \
  -e "ssh -i $VPS_KEY -o StrictHostKeyChecking=accept-new" \
  "$REPO_ROOT/" "$VPS_HOST:$VPS_PATH/"

# VERSION is excluded from the sync (it is per-host), so place it explicitly.
if [[ $DRY_RUN -eq 0 ]]; then
  rsync "${RSYNC_FLAGS[@]}" \
    -e "ssh -i $VPS_KEY -o StrictHostKeyChecking=accept-new" \
    "$REPO_ROOT/backend/VERSION" "$VPS_HOST:$VPS_PATH/backend/VERSION"

  # The built SPA, shipped by its own targeted transfer. Deliberately a SECOND
  # rsync rather than a hole in EXCLUDES: the exclusion is what keeps dist out of
  # --prune's delete list, and that protection must not depend on this step
  # having succeeded.
  #
  # No --delete here either. Vite emits content-hashed asset filenames, so stale
  # assets accumulate rather than break anything (index.html only ever references
  # the current ones), and the downside of a --delete against a bad local dist is
  # the whole SPA going 404. Accumulation is the cheaper failure; sweep dist on
  # the VPS by hand if it ever gets fat.
  log "syncing built frontend -> $VPS_PATH/frontend/dist/"
  rsync "${RSYNC_FLAGS[@]}" \
    -e "ssh -i $VPS_KEY -o StrictHostKeyChecking=accept-new" \
    "$REPO_ROOT/frontend/dist/" "$VPS_HOST:$VPS_PATH/frontend/dist/"
fi

if [[ $DRY_RUN -eq 1 ]]; then
  log "dry run complete — nothing changed"
  exit 0
fi

# ------------------------------------------------------- post-transfer ------
# Every remote assertion below goes through this, so that "the file is not there"
# and "we could not ask" are never the same result. ssh reserves exit 255 for its
# OWN transport failures (host unreachable, auth rejected, connection dropped);
# the remote command's own status comes back verbatim otherwise. Without the
# split, a network blip during verification reads exactly like a clobbered .env —
# and the operator is sent to investigate a production file that is fine.
remote_assert() {
  local expr="$1" what="$2"
  local rc
  set +e
  ssh -i "$VPS_KEY" -o StrictHostKeyChecking=accept-new "$VPS_HOST" "$expr" >/dev/null 2>&1
  rc=$?
  set -e
  case $rc in
    0)   log "verified on remote: $what" ;;
    255) fail "cannot reach $VPS_HOST to verify $what — ssh exited 255 (transport
      failure, not a failed test). The check DID NOT RUN, so production state is
      UNKNOWN. The files have already been transferred; the service has NOT been
      restarted. Re-establish access and re-run before drawing any conclusion." ;;
    *)   return "$rc" ;;
  esac
}

# The .env exclusion is the single most important thing this script does.
# Verify it survived rather than trusting that it did.
log "verifying production .env survived"
remote_assert "test -s $VPS_PATH/backend/.env" "production .env is present and non-empty" \
  || fail "production .env is MISSING OR EMPTY after sync — do NOT restart. Investigate now."

# Same for the SPA: if this is gone, GET / 404s and health stays green.
log "verifying built frontend landed"
remote_assert "test -s $VPS_PATH/frontend/dist/index.html" "frontend/dist/index.html is present" \
  || fail "frontend/dist/index.html is missing — the SPA would 404. Do NOT build on the
      VPS (1GB droplet, OOMs with the engine running). Build here and re-run:
      (cd $REPO_ROOT/frontend && npm run build) && scripts/deploy.sh"

# The remote .venv is EXCLUDED from the sync (it is per-host and platform-specific),
# so a new entry in requirements.txt does not reach the VPS by itself. Before
# 2026-08-02 that was harmless because the dependency set had not changed since the
# venv was built; the moment it does, the next `systemctl restart` boots a process
# that cannot import its own code — and it fails AFTER the restart, i.e. with the
# engine already down and positions unmanaged.
#
# So: install remotely, BEFORE the restart, and treat a failure as a stop. The old
# process is still running and still managing the book at this point, which is
# exactly why this is the safe place to fail. `pip install -r` is a no-op when the
# venv already satisfies the file, so this costs a few seconds on a normal deploy.
log "syncing python dependencies on remote venv"
set +e
dep_out="$(ssh -i "$VPS_KEY" "$VPS_HOST" \
  "cd $VPS_PATH/backend && .venv/bin/pip install --quiet --disable-pip-version-check \
   -r requirements.txt" 2>&1)"
dep_rc=$?
set -e
if [[ $dep_rc -eq 255 ]]; then
  fail "cannot reach $VPS_HOST to install dependencies — ssh exited 255. The files
      are transferred; the service has NOT been restarted, so the running engine is
      untouched and still managing the book. Re-establish access and re-run."
elif [[ $dep_rc -ne 0 ]]; then
  fail "remote dependency install FAILED (exit $dep_rc). NOT restarting — the
      current process is still healthy and managing real positions, whereas a
      restart onto an unsatisfied venv would leave the engine dead on an
      ImportError. Fix and re-run.
      pip said:
$dep_out"
fi

# Prove the interpreter can actually import the app after that install. `pip
# install` succeeding is not the same claim: a wheel can install cleanly and still
# be unimportable on this platform, and the difference only shows up at boot.
log "verifying the remote interpreter can import the app"
remote_assert "cd $VPS_PATH/backend && PT_DISABLE_DOTENV=1 .venv/bin/python -c \
  'import alembic, app.db.migrate'" "app imports on the remote venv" \
  || fail "the remote venv cannot import the application after installing
      requirements.txt. NOT restarting — the running engine is still fine. Debug on
      the box: ssh $VPS_HOST 'cd $VPS_PATH/backend && .venv/bin/python -c \"import app.main\"'"

log "restarting $SERVICE"
ssh -i "$VPS_KEY" "$VPS_HOST" "systemctl restart $SERVICE"

log "waiting for health"
# Tracked so the timeout message can say WHY it timed out. Previously every path
# out of this loop produced the same "did not become healthy" line, whether the
# app was returning 503, the host was unreachable, or the probe itself was broken —
# three very different incidents, one message.
health_code=""; health_status=""; ssh_failures=0; probes=0
for i in $(seq 1 30); do
  probes=$((probes + 1))
  set +e
  health_code="$(ssh -i "$VPS_KEY" "$VPS_HOST" \
    "curl -sS -o /dev/null -w '%{http_code}' $APP_BASE/api/health" 2>/dev/null)"
  ssh_rc=$?
  set -e

  if [[ $ssh_rc -eq 255 ]]; then
    ssh_failures=$((ssh_failures + 1)); sleep 2; continue
  fi
  # /api/health is a readiness probe now (app/engine/readiness.py): 503 while the
  # DB is unreachable, the engine loops are stopped, or the fast risk lane has
  # gone stale. Keep waiting through those — the restart may still be settling —
  # and let the timeout below report the last verdict we saw.
  if [[ "$health_code" != "200" ]]; then
    sleep 2; continue
  fi

  # Read the body BEFORE the GET / probe: a 200 can still mean "starting", i.e.
  # up and serving but with lanes that have not beaten yet. Accepting that would
  # verify nothing — the old loop exited on the first 200, which a process whose
  # risk loop died at startup produces just as readily as a healthy one.
  set +e
  health_body="$(ssh -i "$VPS_KEY" "$VPS_HOST" "curl -fsS $APP_BASE/api/health" 2>/dev/null)"
  body_rc=$?
  set -e
  [[ $body_rc -eq 0 && -n "$health_body" ]] \
    || fail "could not READ /api/health to confirm the deployed commit (exit $body_rc).
      The build identity is unverified — this is not the same as a mismatch, and not
      the same as a pass. Check the box directly."
  health_status="$(printf '%s' "$health_body" | sed -n 's/.*"status":"\([a-z]*\)".*/\1/p')"
  if [[ "$health_status" == "starting" ]]; then
    sleep 2; continue
  fi

  # Health alone is not enough — a 200 health check coexisted with every GET / 404
  # during the .env outage. Check the app root too.
  set +e
  root_code="$(ssh -i "$VPS_KEY" "$VPS_HOST" \
    "curl -sS -o /dev/null -w '%{http_code}' $APP_BASE/" 2>/dev/null)"
  root_rc=$?
  set -e
  [[ $root_rc -ne 255 ]] \
    || fail "health is 200 but the GET / probe could not be RUN (ssh 255). The SPA was
      not verified. Do not treat this deploy as confirmed."
  [[ "$root_code" == "200" ]] \
    || fail "health 200 but GET / returned ${root_code:-<no response>} — frontend serve is broken"

  # Confirm the process is actually running the build we just shipped, rather
  # than an old one that survived a failed restart. (The body was already read
  # above, where the starting/ready verdict is checked.)
  live_sha="$(printf '%s' "$health_body" | sed -n 's/.*"commit":"\([^"]*\)".*/\1/p')"
  [[ -n "$live_sha" ]] \
    || fail "/api/health responded but carries NO \"commit\" field, so the running build
      cannot be identified. Either the endpoint changed shape or the process is running
      code that predates build stamping. Response: $(printf '%s' "$health_body" | head -c 200)"
  [[ "$live_sha" == "$SHA" ]] \
    || fail "deployed $SHA but /api/health reports '$live_sha' — restart did not take"

  log "deployed $BRANCH@$SHA — /api/health is ${health_status:-ready} (DB reachable, both
      engine lanes beating), GET / is 200, and the running build is $live_sha"
  if [[ "$health_status" == "degraded" ]]; then
    log "NOTE: health reports DEGRADED — the deploy is good but something non-fatal is
      wrong (usually an expired Kite token, or the signal lane quiet during market
      hours). Open the cockpit: curl -s $APP_BASE/api/health"
  fi
  log "REMINDER: the engine is DISARMED on every start. ARM from the cockpit when ready."
  exit 0
done

if [[ $ssh_failures -eq $probes ]]; then
  fail "could not reach $VPS_HOST on ANY of $probes health probes (ssh 255 every time).
      The service state is UNKNOWN, not unhealthy — a restart was already issued and
      the new code is on the box. Check connectivity, then verify by hand:
      ssh $VPS_HOST 'systemctl status $SERVICE; curl -sS $APP_BASE/api/health'"
elif [[ $ssh_failures -gt 0 ]]; then
  fail "service did not become healthy within 60s. $ssh_failures of $probes probes could
      not reach the host at all, so the last observed code (${health_code:-none}) is only
      part of the picture. Check: journalctl -u $SERVICE -n 100"
else
  fail "service did not become healthy within 60s — the host was reachable for all
      $probes probes and /api/health last returned ${health_code:-<no response>}
      (readiness verdict: ${health_status:-<none read>}). This is the app failing to
      start, not a network problem. A 503 here names the failed checks in its body —
      read them first: ssh $VPS_HOST 'curl -sS $APP_BASE/api/health'
      Then: journalctl -u $SERVICE -n 100"
fi
