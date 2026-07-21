# VPS Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the live paper-trader backend uninterrupted on a DigitalOcean droplet (Bangalore), reachable from the phone over Tailscale, with the Mac no longer required.

**Architecture:** One systemd-managed uvicorn process serves `/api`, `/ws`, and the built React SPA (same origin). `tailscale serve` fronts it with HTTPS on the tainet; nothing is exposed to the public internet. The droplet's static IP is whitelisted with Kite for outbound order routes. All existing safety gates (arm/kill, disarmed-on-start, daily-loss halt) are untouched.

**Tech Stack:** Python 3 / FastAPI / uvicorn / SQLite, React / Vite build, systemd, Tailscale, DigitalOcean, Zerodha Kite.

## Global Constraints

- **Single live engine, always.** Only ONE process may run `PT_EXECUTION=live` against the Kite account. The Mac's live engine MUST be stopped before the droplet arms. (Two engines duplicate real orders.)
- **Disarmed on every start** — do not change this. A reboot must never auto-trade.
- **Never commit secrets.** `.env`, `access_token.json`, and `*.db` stay off git (already gitignored). Transfer over the tailnet only.
- **Do not touch trading logic, strategy, safety gates, or the ledger model.** This plan only adds SPA serving + a WS-scheme fix + ops.
- **Backend tests are offline/mock only** (`pytest`, `pythonpath=.`, `testpaths=tests`). No test may hit Kite or the network.
- **Owner commit convention:** commits are batched at task boundaries as this plan directs; treat plan execution as the go-ahead for those specific commits. Do not push unless asked.
- **Substitute these operator-supplied values throughout** (define once, reuse):
  - `<DROPLET_IP>` — the droplet's static public IPv4.
  - `<TAILNET>` — your tailnet's MagicDNS suffix, e.g. `tailXXXX.ts.net`.
  - `<APP_HOST>` — the droplet's tailnet hostname; this plan uses `paper-trader`, so the URL is `https://paper-trader.<TAILNET>`.
  - `<DEPLOY_DIR>` — install path on the droplet; this plan uses `/opt/paper-trader`.
  - `<TS_AUTHKEY>` — a one-off Tailscale auth key.

---

## Task 1: Backend serves the built SPA (same origin, env-gated)

**Files:**
- Modify: `backend/app/core/config.py:205-214` (add two settings)
- Modify: `backend/app/main.py` (imports + SPA mount after routers)
- Test: `backend/tests/test_spa_serving.py` (create)

**Interfaces:**
- Consumes: existing `get_settings()`, the mounted `routes.router` / `backtest_routes.router`, `/api/health`.
- Produces: `Settings.serve_frontend: bool` (env `PT_SERVE_FRONTEND`), `Settings.frontend_dist: str` (env `PT_FRONTEND_DIST`). When `serve_frontend` is true and `frontend_dist` is a real dir, the app serves `index.html` at `/` and as SPA fallback, and static files under it, WITHOUT shadowing `/api` or `/ws`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_spa_serving.py`:

```python
"""SPA serving is env-gated and must never shadow /api or /ws (PT_SERVE_FRONTEND)."""
import importlib

from fastapi.testclient import TestClient


def _build_app(tmp_path, monkeypatch, *, serve: bool):
    # a fake built frontend
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>PT</title>")
    (dist / "assets" / "app.js").write_text("console.log('pt')")

    monkeypatch.setenv("PT_PROVIDER", "mock")
    monkeypatch.setenv("PT_SERVE_FRONTEND", "1" if serve else "0")
    monkeypatch.setenv("PT_FRONTEND_DIST", str(dist))

    # get_settings() is lru_cache'd and main.py builds routes at import time,
    # so reload both to pick up the env for this test.
    from app.core import config
    config.get_settings.cache_clear()
    import app.main as main
    importlib.reload(main)
    return main.app


# NOTE: build the client WITHOUT the `with` context manager, matching the
# codebase convention — that skips the engine lifespan (which deadlocked the
# full suite in other tests) and these SPA routes don't need app.state.runner.

def test_spa_served_at_root(tmp_path, monkeypatch):
    c = TestClient(_build_app(tmp_path, monkeypatch, serve=True))
    r = c.get("/")
    assert r.status_code == 200
    assert "<!doctype html>" in r.text.lower()


def test_spa_fallback_for_client_route(tmp_path, monkeypatch):
    c = TestClient(_build_app(tmp_path, monkeypatch, serve=True))
    r = c.get("/some/deep/client-route")
    assert r.status_code == 200
    assert "<title>PT</title>" in r.text


def test_static_asset_served(tmp_path, monkeypatch):
    c = TestClient(_build_app(tmp_path, monkeypatch, serve=True))
    r = c.get("/assets/app.js")
    assert r.status_code == 200
    assert "console.log" in r.text


def test_api_not_shadowed(tmp_path, monkeypatch):
    c = TestClient(_build_app(tmp_path, monkeypatch, serve=True))
    assert c.get("/api/health").json() == {"ok": True}
    # unknown /api path must 404 as JSON, NOT the SPA index
    r = c.get("/api/does-not-exist")
    assert r.status_code == 404
    assert "<!doctype html>" not in r.text.lower()


def test_serving_off_by_default(tmp_path, monkeypatch):
    c = TestClient(_build_app(tmp_path, monkeypatch, serve=False))
    # health still works; root is NOT the SPA (404 with no catch-all)
    assert c.get("/api/health").json() == {"ok": True}
    assert c.get("/").status_code == 404
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_spa_serving.py -v`
Expected: FAIL — `PT_SERVE_FRONTEND`/`PT_FRONTEND_DIST` not on `Settings`, no SPA routes.

- [ ] **Step 3: Add the two settings**

In `backend/app/core/config.py`, immediately after the `frontend_url` field (line 203):

```python
    # ── production SPA serving (single-process deploy) ──────────────────────
    # When true and frontend_dist is a real directory, FastAPI serves the built
    # React bundle at / (and as SPA fallback) alongside /api and /ws — one origin,
    # one process. Off by default so dev/tests keep the two-process Vite setup.
    serve_frontend: bool = False          # env: PT_SERVE_FRONTEND
    frontend_dist: str = ""               # env: PT_FRONTEND_DIST (abs path to dist/)
```

- [ ] **Step 4: Add SPA serving in `main.py`**

In `backend/app/main.py`, extend the imports (after line 15):

```python
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
```

(`JSONResponse` is already imported — merge it into the one import line; add `FileResponse`.)

Then at the END of the file (after `app.include_router(...)` and the `/api/health` route, so this catch-all is registered last):

```python
# ── production: serve the built React SPA from the same origin ──────────────
# Registered LAST so the API routers and /api/health match first. Off unless
# PT_SERVE_FRONTEND=1 and PT_FRONTEND_DIST points at a real dist/ directory.
_spa_settings = get_settings()
if _spa_settings.serve_frontend and os.path.isdir(_spa_settings.frontend_dist):
    _DIST = _spa_settings.frontend_dist
    _ASSETS = os.path.join(_DIST, "assets")
    if os.path.isdir(_ASSETS):
        app.mount("/assets", StaticFiles(directory=_ASSETS), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # Never hijack the API or WebSocket surfaces.
        if full_path.startswith("api/") or full_path == "api" or full_path.startswith("ws"):
            return JSONResponse({"error": "not found"}, status_code=404)
        candidate = os.path.join(_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_DIST, "index.html"))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_spa_serving.py -v`
Expected: PASS (5 passed).

- [ ] **Step 6: Run the full suite to confirm no regression**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: all pass (SPA off by default, so existing tests are unaffected).

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/config.py backend/app/main.py backend/tests/test_spa_serving.py
git commit -m "feat(deploy): FastAPI serves built SPA same-origin, env-gated (PT_SERVE_FRONTEND)"
```

---

## Task 2: Frontend WebSocket scheme fix (wss on HTTPS)

**Files:**
- Modify: `frontend/src/state/LiveContext.tsx:29`
- Modify: `frontend/src/views/WatchlistView.tsx:334`

**Interfaces:**
- Consumes: `location.protocol`, `location.host`.
- Produces: WS URLs that use `wss://` when the page is HTTPS, `ws://` otherwise. No behavioural change on `http://` dev.

- [ ] **Step 1: Fix `LiveContext.tsx`**

Replace the WS construction at `frontend/src/state/LiveContext.tsx:28-30`:

```ts
      const wsScheme = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(
        `${wsScheme}://${location.host}/ws${TOKEN ? `?token=${encodeURIComponent(TOKEN)}` : ''}`,
      )
```

- [ ] **Step 2: Fix `WatchlistView.tsx`**

Replace the per-instrument WS construction at `frontend/src/views/WatchlistView.tsx:333-335`:

```ts
      const wsScheme = location.protocol === 'https:' ? 'wss' : 'ws'
      `${wsScheme}://${location.host}/ws/instrument/${k}${TOKEN ? `?token=${encodeURIComponent(TOKEN)}` : ''}`,
```

(Keep the surrounding `new WebSocket(...)` call intact — only the URL string and the added `wsScheme` line change. Match the existing indentation.)

- [ ] **Step 3: Typecheck (frontend has no unit tests)**

Run: `cd frontend && npm run typecheck`
Expected: no errors.

- [ ] **Step 4: Verify a production build succeeds**

Run: `cd frontend && npm run build`
Expected: build completes, `frontend/dist/index.html` and `frontend/dist/assets/` exist.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/state/LiveContext.tsx frontend/src/views/WatchlistView.tsx
git commit -m "fix(frontend): derive WS scheme from page protocol (wss on https)"
```

---

## Task 3: Provision & harden the droplet

**Owner prerequisite (do first):** Create a DigitalOcean droplet — region **Bangalore (BLR1)**, image **Ubuntu 24.04 LTS**, size 1 GB / 1 vCPU (~$6/mo), add your SSH key. Note its static IPv4 as `<DROPLET_IP>`. If a floating/reserved IP is used, that reserved IP is the one to whitelist with Kite.

**Files:** none in-repo (remote host config).

- [ ] **Step 1: SSH in and confirm reachability**

Run (from the Mac): `ssh root@<DROPLET_IP> 'echo ok && lsb_release -d'`
Expected: `ok` and `Ubuntu 24.04`.

- [ ] **Step 2: Base packages + timezone (IST)**

```bash
ssh root@<DROPLET_IP> 'apt-get update && apt-get install -y python3-venv python3-pip git sqlite3 nodejs npm ufw && timedatectl set-timezone Asia/Kolkata && date'
```
Expected: installs succeed; `date` prints an IST (`+0530`) timestamp.

- [ ] **Step 3: Create an unprivileged deploy user**

```bash
ssh root@<DROPLET_IP> 'id deploy || (useradd -m -s /bin/bash deploy && install -d -o deploy -g deploy /opt/paper-trader)'
```
Expected: user `deploy` exists; `<DEPLOY_DIR>` (`/opt/paper-trader`) is owned by `deploy`.

- [ ] **Step 4: Firewall — SSH only, no app ports public**

```bash
ssh root@<DROPLET_IP> 'ufw allow OpenSSH && ufw --force enable && ufw status verbose'
```
Expected: `Status: active`; only 22/OpenSSH allowed. (The app is never exposed publicly — Tailscale handles access. Tailscale does not require an inbound UFW rule; it uses NAT traversal.)

- [ ] **Step 5: Commit (runbook note only — no repo change)**

No repo change in this task. Record `<DROPLET_IP>` in the design doc's checklist if useful. Proceed.

---

## Task 4: Join Tailscale and configure HTTPS serve

**Owner prerequisite:** In the Tailscale admin console → Settings → Keys, generate a one-off (or reusable, ephemeral-off) **auth key** → `<TS_AUTHKEY>`. Ensure MagicDNS and HTTPS certificates are enabled for the tailnet (Admin → DNS → enable MagicDNS + HTTPS).

- [ ] **Step 1: Install Tailscale and join the tainet**

```bash
ssh root@<DROPLET_IP> 'curl -fsSL https://tailscale.com/install.sh | sh && tailscale up --authkey <TS_AUTHKEY> --hostname paper-trader --ssh'
# joins the tailnet as the node "paper-trader"
ssh root@<DROPLET_IP> 'tailscale status && tailscale ip -4'
```
Expected: the node appears as `paper-trader`; `tailscale status` lists your other devices; a `100.x.y.z` tailnet IP prints. Approve the machine in the admin console if required.

- [ ] **Step 2: Confirm the phone can reach the node**

From the phone (Tailscale ON), ping/open `http://paper-trader.<TAILNET>` — nothing serves yet, so expect connection refused (NOT DNS failure). DNS resolving proves MagicDNS + tailnet routing work.

- [ ] **Step 3: Configure `tailscale serve` to front the backend over HTTPS**

Deferred until the service is running (Task 6, Step 4) — `tailscale serve` needs a live upstream on `127.0.0.1:8090`. Recorded here so the dependency is explicit.

---

## Task 5: Deploy the code, build the frontend, write secrets

**Files:** remote only, under `<DEPLOY_DIR>`.

- [ ] **Step 1: Get the code onto the droplet**

Option A (git, if the repo is reachable): as `deploy`,
```bash
ssh deploy@<DROPLET_IP> 'cd /opt/paper-trader && git clone <YOUR_REPO_URL> . && git checkout main'
```
Option B (no remote): from the Mac, copy the two app dirs over the tailnet (excludes big/ignored files):
```bash
rsync -av --exclude .venv --exclude node_modules --exclude '*.db*' --exclude 'access_token.json' \
  paper-trader/backend paper-trader/frontend paper-trader/strategies \
  deploy@paper-trader.<TAILNET>:/opt/paper-trader/
```
Expected: `backend/`, `frontend/` present under `<DEPLOY_DIR>`.

- [ ] **Step 2: Backend venv + deps**

```bash
ssh deploy@<DROPLET_IP> 'cd /opt/paper-trader/backend && python3 -m venv .venv && .venv/bin/pip install -U pip && .venv/bin/pip install -r requirements.txt'
```
Expected: install succeeds; `.venv/bin/uvicorn --version` works.

- [ ] **Step 3: Write `backend/.env` (secrets — perms 0600)**

Create `<DEPLOY_DIR>/backend/.env` on the droplet with (fill real values; keep `PT_EXECUTION` **empty** for now so the first boot is paper-safe):

```ini
PT_PROVIDER=kite
KITE_API_KEY=<your key>
KITE_API_SECRET=<your secret>
PT_API_TOKEN=<generate a strong random token>
PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY
PT_EXECUTION=
PT_SERVE_FRONTEND=1
PT_FRONTEND_DIST=/opt/paper-trader/frontend/dist
PT_FRONTEND_URL=/
# optional:
# TELEGRAM_BOT_TOKEN=...
# TELEGRAM_CHAT_ID=...
```

Then lock it down:
```bash
ssh deploy@<DROPLET_IP> 'chmod 600 /opt/paper-trader/backend/.env'
```
Expected: `.env` is `-rw-------`.

- [ ] **Step 4: Build the frontend with the matching token baked in**

The bundle reads `import.meta.env.VITE_PT_TOKEN`; it must equal `PT_API_TOKEN`:
```bash
ssh deploy@<DROPLET_IP> 'cd /opt/paper-trader/frontend && npm ci && VITE_PT_TOKEN=<same PT_API_TOKEN> npm run build'
```
Expected: `frontend/dist/index.html` + `frontend/dist/assets/` exist. (Rebuild whenever `PT_API_TOKEN` is rotated.)

---

## Task 6: systemd service (auto-restart, disarmed on start)

**Files:**
- Create (remote): `/etc/systemd/system/paper-trader.service`

- [ ] **Step 1: Write the unit file**

Create `/etc/systemd/system/paper-trader.service`:

```ini
[Unit]
Description=Options Paper Trader (FastAPI engine + SPA)
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
User=deploy
Group=deploy
WorkingDirectory=/opt/paper-trader/backend
EnvironmentFile=/opt/paper-trader/backend/.env
ExecStart=/opt/paper-trader/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8090
Restart=always
RestartSec=5
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Enable and start**

```bash
ssh root@<DROPLET_IP> 'systemctl daemon-reload && systemctl enable --now paper-trader && sleep 3 && systemctl --no-pager status paper-trader'
```
Expected: `active (running)`.

- [ ] **Step 3: Verify locally on the droplet (health + SPA, still paper-safe)**

```bash
ssh root@<DROPLET_IP> 'curl -s localhost:8090/api/health && echo && curl -s localhost:8090/ | head -c 80'
```
Expected: `{"ok":true}` then the SPA `index.html` opening bytes. Logs should show the engine started **disarmed** and NOT `🔴 LIVE EXECUTION ENABLED` (execution is still empty).

- [ ] **Step 4: Point `tailscale serve` at the backend (HTTPS)**

```bash
ssh root@<DROPLET_IP> 'tailscale serve --bg --https=443 http://127.0.0.1:8090 && tailscale serve status'
```
Expected: serve status shows `https://paper-trader.<TAILNET>` → `http://127.0.0.1:8090`.

- [ ] **Step 5: Verify end-to-end from the phone**

From the phone (Tailscale ON), open `https://paper-trader.<TAILNET>`.
Expected: the cockpit loads (valid cert), REST works, and the live `/ws` connects (badge/heartbeat updates) — proving `wss://` (Task 2) works over HTTPS.

---

## Task 7: Kite console + first live-capable login (owner)

**Owner actions in the Kite developer console (kite.trade):**

- [ ] **Step 1: Whitelist the droplet IP**

Add `<DROPLET_IP>` (or the reserved IP) to the app's whitelisted IPs for order routes. Keep the home IP for now; remove it after cutover is verified.

- [ ] **Step 2: Set the redirect URL**

Set the app's redirect URL to `https://paper-trader.<TAILNET>/api/session`.
(Flow: `/api/login` → Kite → `/api/session?request_token=…` → token captured → bounce to `PT_FRONTEND_URL` (`/`).)

- [ ] **Step 3: Log in from the phone**

On `https://paper-trader.<TAILNET>`, tap **Connect Kite**, complete Zerodha login.
Expected: redirect returns to the cockpit; `access_token.json` is written on the droplet:
```bash
ssh deploy@<DROPLET_IP> 'ls -l /opt/paper-trader/backend/access_token.json && cat /opt/paper-trader/backend/access_token.json'
```
Expected: today's date + a token. Provider-health in the UI should go green.

---

## Task 8: Data cutover (flat) + go live

**Precondition:** the account book is **flat** (no open positions) — do this on a weekend or after square-off. If positions are open, the copied book must exactly match real holdings (see design doc "Data & cutover safety").

- [ ] **Step 1: Stop the Mac's live engine (enforce single-live-engine)**

On the Mac, stop the running backend (Ctrl-C / kill the uvicorn). Confirm it is down before proceeding. From now on the droplet is the only engine.

- [ ] **Step 2: Copy the live ledger to the droplet**

On the Mac, checkpoint WAL then copy the DB over the tailnet:
```bash
cd paper-trader/backend
.venv/bin/python -c "import sqlite3; sqlite3.connect('paper_trader.db').execute('PRAGMA wal_checkpoint(TRUNCATE)')"
scp paper_trader.db deploy@paper-trader.<TAILNET>:/opt/paper-trader/backend/paper_trader.db
```
Expected: `paper_trader.db` present on the droplet.

- [ ] **Step 3: Verify the ledger invariant on the droplet**

```bash
ssh deploy@<DROPLET_IP> 'cd /opt/paper-trader/backend && .venv/bin/python scripts/dryrun.py 50'
```
Expected: the dry-run asserts `cash == initial + realized − Σ(open entry_cost)` to the paisa with no failure. (This runs the mock provider — it validates ledger arithmetic, not live trading.)

- [ ] **Step 4: Flip execution to live**

Edit `/opt/paper-trader/backend/.env`: set `PT_EXECUTION=live`. Then:
```bash
ssh root@<DROPLET_IP> 'systemctl restart paper-trader && sleep 3 && journalctl -u paper-trader -n 30 --no-pager | grep -i "live execution" '
```
Expected: logs print `🔴 LIVE EXECUTION ENABLED`. The engine is live-capable but still **disarmed**.

- [ ] **Step 5: Re-auth Kite (fresh process needs today's token) and ARM**

On the phone: tap **Connect Kite** if the token isn't current, confirm provider health green, verify the book matches reality, then **ARM** from the cockpit.
Expected: armed; the engine may now open positions. KILL disarms + squares off.

---

## Task 9: Backups

**Files:**
- Create (remote): `/opt/paper-trader/backup.sh`, a `deploy` crontab entry.

- [ ] **Step 1: Backup script**

Create `/opt/paper-trader/backup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
DIR=/opt/paper-trader/backups
mkdir -p "$DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
sqlite3 /opt/paper-trader/backend/paper_trader.db ".backup '$DIR/paper_trader-$STAMP.db'"
# keep the last 14
ls -1t "$DIR"/paper_trader-*.db | tail -n +15 | xargs -r rm -f
```
```bash
ssh deploy@<DROPLET_IP> 'chmod +x /opt/paper-trader/backup.sh'
```

- [ ] **Step 2: Nightly cron (after square-off, 20:00 IST)**

```bash
ssh deploy@<DROPLET_IP> '(crontab -l 2>/dev/null; echo "0 20 * * * /opt/paper-trader/backup.sh") | crontab - && crontab -l'
```
Expected: the cron line is listed.

- [ ] **Step 3: Prove it works once**

```bash
ssh deploy@<DROPLET_IP> '/opt/paper-trader/backup.sh && ls -l /opt/paper-trader/backups'
```
Expected: a timestamped `.db` backup exists.

- [ ] **Step 4 (owner): Enable DigitalOcean weekly snapshots**

In the DO console, enable weekly backups/snapshots for the droplet as a coarse second line of defence.

---

## Post-cutover verification checklist

- [ ] `systemctl status paper-trader` = active; survives `reboot` and comes up **disarmed**.
- [ ] `https://paper-trader.<TAILNET>` loads from the phone on cellular (Mac off): UI + live WS.
- [ ] Kite login completes from the phone; order routes accept `<DROPLET_IP>`.
- [ ] `scripts/dryrun.py` ledger invariant holds on the droplet.
- [ ] Exactly one live engine (Mac engine confirmed stopped).
- [ ] A backup file exists under `/opt/paper-trader/backups`.
