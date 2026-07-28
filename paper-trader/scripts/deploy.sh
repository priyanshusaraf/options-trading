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

# Guard 0: the excludes must actually contain .env. Cheap insurance against a
# future edit quietly removing the line that has already cost an outage.
# (Match the array ELEMENT — shell quoting means the element is `.env`, with no
# literal quote characters in it.)
printf '%s\n' "${EXCLUDES[@]}" | grep -qx -- '--exclude' || fail "EXCLUDES malformed"
printf '%s\n' "${EXCLUDES[@]}" | grep -qx -- '\.env'     || fail ".env is not excluded — refusing"
printf '%s\n' "${EXCLUDES[@]}" | grep -qx -- 'frontend/dist' \
  || fail "frontend/dist is not excluded — a prune would 404 the whole SPA. Refusing."
# The live .db.lock and the .db.predeploy-* ledger snapshots have a DOT before the
# suffix, so *.db-* misses them entirely. Assert the dot-glob is present.
printf '%s\n' "${EXCLUDES[@]}" | grep -qx -- '\*\.db\.\*' \
  || fail "'*.db.*' is not excluded — .db.lock and .db.predeploy-* would be pushed, and
      a --prune would delete the live ones. Refusing."

# Guard 1: never deploy into a live session by accident.
# NSE/BSE cash + F&O trade 09:15-15:30 IST, Mon-Fri; buffered to 09:00-15:45.
if [[ $FORCE_MARKET_HOURS -eq 0 ]]; then
  ist_now="$(TZ=Asia/Kolkata date '+%u %H%M')"
  dow="${ist_now%% *}"; hhmm="${ist_now##* }"
  if [[ "$dow" -le 5 ]] && [[ "10#$hhmm" -ge 900 ]] && [[ "10#$hhmm" -le 1545 ]]; then
    fail "market hours (IST $hhmm, day $dow). Deploy in a closed window, or pass --force-market-hours."
  fi
fi

# Guard 2: know exactly what is shipping. A dirty tree is refused outright —
# there is no override. The whole point of stamping build_sha onto every trade is
# that the SHA can be checked out and diffed later; "abc1234-dirty" cannot.
cd "$REPO_ROOT"
command -v git >/dev/null || fail "git not found"
SHA="$(git rev-parse --short HEAD)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
# --porcelain, not diff-index: untracked files are rsynced too, so an untracked
# .py ships code that is not in $SHA — the same untraceability, one step sideways.
# (Gitignored files, incl. backend/VERSION, do not appear here.)
if [[ -n "$(git status --porcelain)" ]]; then
  git status --short >&2
  fail "working tree is dirty (modified or untracked). Commit — or gitignore — before
      deploying. Uncommitted code cannot be identified from trades.build_sha, and
      this ledger is the record of real money."
fi

# Guard 3: tests must be green before anything touches production. Both suites:
# pytest.ini sets testpaths=tests, so research_tests/ needs naming explicitly.
log "running backend suite (tests + research_tests)"
( cd "$REPO_ROOT/backend" && .venv/bin/python -m pytest tests research_tests --tb=short ) \
  > /tmp/pt-deploy-tests.log 2>&1 \
  || { tail -40 /tmp/pt-deploy-tests.log; fail "tests failed — see /tmp/pt-deploy-tests.log"; }

log "running ledger reconciliation"
( cd "$REPO_ROOT/backend" && .venv/bin/python scripts/dryrun.py 700 ) \
  > /tmp/pt-deploy-dryrun.log 2>&1 \
  || { tail -40 /tmp/pt-deploy-dryrun.log; fail "dryrun/ledger invariant failed"; }

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

if [[ $PRUNE -eq 1 ]]; then
  log "PRUNE: computing what would be DELETED on the remote"
  # --delete respects --exclude (excluded files are protected, not removed), so
  # this lists only genuinely untracked-and-unprotected remote paths.
  prune_list="$(rsync "${RSYNC_FLAGS[@]}" --delete --dry-run "${EXCLUDES[@]}" \
    -e "ssh -i $VPS_KEY -o StrictHostKeyChecking=accept-new" \
    "$REPO_ROOT/" "$VPS_HOST:$VPS_PATH/" 2>&1 | grep '^deleting ' || true)"

  if [[ -z "$prune_list" ]]; then
    log "nothing to prune — proceeding as a normal deploy"
    PRUNE=0
  else
    echo
    printf '\033[1;31mThese remote files will be PERMANENTLY DELETED:\033[0m\n'
    echo "$prune_list" | sed 's/^deleting /  - /'
    echo
    printf 'Count: %s\n\n' "$(echo "$prune_list" | wc -l | tr -d ' ')"
    read -r -p "Type 'delete' to confirm, anything else to abort: " confirm
    [[ "$confirm" == "delete" ]] || fail "prune aborted — nothing was changed"
    RSYNC_FLAGS+=(--delete)
  fi
fi

write_version

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
# The .env exclusion is the single most important thing this script does.
# Verify it survived rather than trusting that it did.
log "verifying production .env survived"
ssh -i "$VPS_KEY" "$VPS_HOST" "test -s $VPS_PATH/backend/.env" \
  || fail "production .env is MISSING OR EMPTY after sync — do NOT restart. Investigate now."

# Same for the SPA: if this is gone, GET / 404s and health stays green.
log "verifying built frontend landed"
ssh -i "$VPS_KEY" "$VPS_HOST" "test -s $VPS_PATH/frontend/dist/index.html" \
  || fail "frontend/dist/index.html is missing — the SPA would 404. Do NOT build on the
      VPS (1GB droplet, OOMs with the engine running). Build here and re-run:
      (cd $REPO_ROOT/frontend && npm run build) && scripts/deploy.sh"

log "restarting $SERVICE"
ssh -i "$VPS_KEY" "$VPS_HOST" "systemctl restart $SERVICE"

log "waiting for health"
for i in $(seq 1 30); do
  if ssh -i "$VPS_KEY" "$VPS_HOST" \
       "curl -fsS -o /dev/null -w '%{http_code}' $APP_BASE/api/health" \
       2>/dev/null | grep -q '^200$'; then
    # Health alone is not enough — a 200 health check coexisted with every GET / 404
    # during the .env outage. Check the app root too.
    root_code="$(ssh -i "$VPS_KEY" "$VPS_HOST" \
      "curl -sS -o /dev/null -w '%{http_code}' $APP_BASE/ || true")"
    [[ "$root_code" == "200" ]] || fail "health 200 but GET / returned $root_code — frontend serve is broken"

    # Confirm the process is actually running the build we just shipped, rather
    # than an old one that survived a failed restart.
    live_sha="$(ssh -i "$VPS_KEY" "$VPS_HOST" \
      "curl -fsS $APP_BASE/api/health" 2>/dev/null \
      | sed -n 's/.*"commit":"\([^"]*\)".*/\1/p')"
    [[ "$live_sha" == "$SHA" ]] \
      || fail "deployed $SHA but /api/health reports '${live_sha:-none}' — restart did not take"

    log "deployed $BRANCH@$SHA — healthy, and /api/health confirms $live_sha"
    log "REMINDER: the engine is DISARMED on every start. ARM from the cockpit when ready."
    exit 0
  fi
  sleep 2
done

fail "service did not become healthy within 60s — check: journalctl -u $SERVICE -n 100"
