# VPS Deployment — Design

**Date:** 2026-07-10
**Status:** Approved (design); implementation plan to follow
**Owner:** priyanshusaraf

## Problem

The live paper-trader currently runs on the owner's Mac: FastAPI backend on `:8090`
and a Vite dev server on `:5173` bound to the Tailscale IP. This means:

- The Mac must stay awake (`caffeinate`) and online for the engine to run.
- Home wifi outages interrupt a **real-money** trading engine.
- The static IP whitelisted with Kite is a home/residential IP, which is not stable.

Goal: move the always-on backend to a VPS so it runs uninterrupted, keep accessing the
UI from the phone **from anywhere**, and keep the real-money safety posture intact.

## Non-goals

- No change to trading logic, strategy, safety gates, arm/kill, or the ledger model.
- No public exposure of the trading UI (stays private).
- No headless/automated Kite login (violates Kite ToS — daily re-auth stays a manual tap).
- No containerization (Docker) — out of scope; systemd is sufficient and simpler.

## Target architecture

```
   Phone (anywhere: cellular / any wifi)  — Tailscale app ON, WireGuard-encrypted
        │
        ▼   https://paper-trader.<tailnet>.ts.net   (MagicDNS, tailnet-only)
   ┌──── DigitalOcean droplet (Bangalore BLR1, Ubuntu 24.04, static public IP) ─────┐
   │                                                                                 │
   │   tailscale serve  (HTTPS termination, free *.ts.net cert, proxies WS)          │
   │        │                                                                        │
   │        ▼                                                                        │
   │   uvicorn / FastAPI  @ 127.0.0.1:8090   — ONE systemd service, Restart=always   │
   │        ├── /api/*   REST   (gated by PT_API_TOKEN)                              │
   │        ├── /ws , /ws/instrument/{key}   engine state + ticks                    │
   │        └── /  (+ SPA fallback)   built React bundle (static files)              │
   │                                                                                 │
   │   SQLite paper_trader.db · access_token.json · backend/.env (secrets, 0600)     │
   │   TZ = Asia/Kolkata                                                             │
   └──────────────────────────────┬──────────────────────────────────────────────────┘
                                   │  outbound from the static IP
                                   ▼
                        Zerodha Kite API  (droplet IP whitelisted for order routes)
```

**Exposure model:** uvicorn binds to `127.0.0.1` only. The UI is reachable *exclusively*
through `tailscale serve` on the tailnet — never on `0.0.0.0`, never on the public
internet. The droplet's static IP is used only *outbound* to reach Kite, and that is the
IP whitelisted in the Kite console. No inbound public ports for the app (only SSH, ideally
also restricted to the tailnet / SSH keys).

## Components & responsibilities

### 1. Single production process (collapse frontend into backend)
Today there are two processes (uvicorn + `npm run dev`). In production we build the
frontend once and let FastAPI serve it, giving one process, one port, one origin.

- **Build:** `npm run build` → `frontend/dist/`.
- **Serve:** add to `backend/app/main.py`, *after* all routers are included so it never
  shadows `/api` or `/ws`:
  - Mount `StaticFiles` for the built assets.
  - A catch-all SPA fallback route that returns `index.html` for any non-`/api`, non-`/ws`
    path (so client-side routing / refresh works).
  - Guard with an env flag (e.g. `PT_SERVE_FRONTEND=1` + `PT_FRONTEND_DIST=/path/to/dist`)
    so dev/tests are unaffected when the flag is off.
- **Consequence:** same-origin → CORS becomes moot in production; Kite's redirect lands
  back on the same origin. `settings.frontend_url` / `PT_FRONTEND_URL` set to the tailnet
  HTTPS URL (or `/` since same-origin).

**Interface:** the frontend already calls **relative** `/api/...` (`lib/api.ts`) and builds
WS URLs from `location.host` (`LiveContext.tsx`, `WatchlistView.tsx`), so a same-origin
build needs no host wiring — see the one required fix below.

### 2. WebSocket scheme fix (required for HTTPS)
The frontend hardcodes `ws://${location.host}/ws`. Under `https://…ts.net`, browsers block
`ws://` as mixed content. Fix (2 sites): derive the scheme from the page protocol.

```ts
const wsScheme = location.protocol === 'https:' ? 'wss' : 'ws'
// `${wsScheme}://${location.host}/ws...`
```

- `frontend/src/state/LiveContext.tsx:29`
- `frontend/src/views/WatchlistView.tsx:334`

This is also a plain correctness improvement (should always be `wss` on secure pages).

### 3. Process management — systemd
One unit, e.g. `paper-trader.service`:
- `ExecStart=/…/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8090`
- `WorkingDirectory=/…/backend`, `EnvironmentFile=/…/backend/.env`
- `Restart=always`, `RestartSec=5`, `TimeoutStopSec` generous enough for a clean shutdown.
- Runs as a non-root deploy user.
- **Disarmed on every start** (existing behaviour) → a droplet reboot never auto-trades.

`tailscale serve` is configured once (persisted) to front `127.0.0.1:8090` over HTTPS.

### 4. Tailscale
- Droplet joins the existing tailnet via a **one-off auth key** (non-interactive
  `tailscale up --authkey=…`), then approved in the admin console.
- MagicDNS hostname (e.g. `paper-trader`) → stable URL `https://paper-trader.<tailnet>.ts.net`.
- Phone already runs Tailscale; works over cellular and any wifi ⇒ "from anywhere".

### 5. Secrets & Kite token
- `backend/.env` on the droplet (perms `0600`, never committed): `KITE_API_KEY`,
  `KITE_API_SECRET`, `PT_PROVIDER=kite`, `PT_EXECUTION=live`,
  `PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY`, `PT_API_TOKEN=<strong secret>`,
  `PT_SERVE_FRONTEND=1`, `PT_FRONTEND_DIST=…`, optional `TELEGRAM_*`.
- `access_token.json` written by the running backend after the daily **Connect Kite** tap;
  survives restarts. Re-auth is a manual phone tap each morning (token expires ~06:00 IST).
- Transfer secrets via `scp` over the tailnet or paste directly on the box — never through git.
- **Frontend API token is build-time.** The bundle reads `import.meta.env.VITE_PT_TOKEN`
  (`lib/api.ts`, `LiveContext.tsx`, `WatchlistView.tsx`), so `npm run build` must run with
  `VITE_PT_TOKEN` set equal to the backend's `PT_API_TOKEN`; the token is baked into the JS
  (acceptable — the bundle is served tailnet-only). Rotating `PT_API_TOKEN` requires a rebuild.
  Build step: `VITE_PT_TOKEN=$PT_API_TOKEN npm run build`.

### 6. Timezone
Set the droplet to `Asia/Kolkata` (`timedatectl set-timezone Asia/Kolkata`) so market-hours,
square-off, and daily-snapshot logic match IST without relying on code assumptions.

## Data & cutover safety (real money — the delicate part)

- `paper_trader.db` holds **real realized P&L and any open positions**. In non-mock mode the
  book carries across restarts, so the VPS book must reflect the real account exactly.
- **Preferred cutover: when flat.** Do it on a weekend or after square-off with zero open
  positions. Steps:
  1. Stop the Mac's live engine (so only one engine can ever be live — see below).
  2. Copy `paper_trader.db` (+ `-wal`/`-shm` flushed) to the droplet.
  3. Verify the ledger invariant on the droplet: `scripts/dryrun.py` asserts
     `cash == initial + realized − Σ(open entry_cost)` to the paisa.
  4. Start the service **disarmed**, re-auth Kite, confirm provider health, then arm.
- If positions are open at cutover, the copied book must match the real account holdings
  exactly (same rule as the original go-live) — otherwise the risk loop will place real
  orders to flatten phantom rows.

### Single-live-engine invariant (critical)
Only ONE process may run with `PT_EXECUTION=live` against the Kite account at any time.
Two live engines would both mark/exit the shared book and duplicate real orders. The
cutover MUST stop the Mac's live engine before the droplet arms. During a transition the
Mac may run in paper/observer mode, but never a second live engine.

## Backups
- Nightly cron: `sqlite3 paper_trader.db ".backup '/…/backups/paper_trader-$(date).db'"`,
  keep N days (rotate). (Cron provides the timestamp; the app itself never calls
  `Date.now()`-style clocks for this.)
- DigitalOcean weekly droplet snapshots as a coarse second line of defence.
- Keep the existing pre-cutover `.sql` ledger dump convention.

## Kite console changes (owner-only, manual)
1. **Whitelist the droplet's static IP** for order routes (home IP can be removed once
   cutover is verified).
2. **Update the redirect URL** to `https://paper-trader.<tailnet>.ts.net/api/session`
   (the OAuth callback — `/api/login` → Kite → `/api/session?request_token=…` → captures
   token → bounces to frontend). The phone browser is on the tailnet, so it resolves the
   `*.ts.net` redirect target.

## What stays unchanged
- All safety gates: arm/disarm, kill switch + square-off, daily-loss halt, adaptive routing,
  ownership guard, `SafePaperKite` allowlist, two-gate live selection.
- Disarmed-on-start.
- Strategy, backtests, charges model, DB schema, API surface.
- Phone access pattern (Tailscale), just pointed at the droplet instead of the Mac.

## Alternatives considered
- **Two processes + Caddy reverse proxy** (no app-code change): rejected — the ~15-line
  same-origin serve in FastAPI is simpler at runtime (one service) and removes CORS. Caddy
  remains the fallback if we ever want the frontend fully decoupled.
- **Plain-HTTP bind to the tailscale IP** (no `wss` fix): rejected — HTTPS via
  `tailscale serve` gives a clean `https://…ts.net` URL with a free cert, and the `wss` fix
  is trivial and correct regardless. (WireGuard already encrypts either way.)
- **Public HTTPS + login / Cloudflare Tunnel**: rejected for a real-money UI — Tailscale-only
  keeps the dashboard off the public internet entirely.
- **Docker**: rejected — single SQLite + single Python process is simpler under systemd.

## Risks & mitigations
- *Two live engines* → duplicate real orders. Mitigation: single-live-engine invariant;
  stop the Mac before arming the droplet.
- *Wrong book at cutover* → phantom-flatten real orders. Mitigation: cut over flat; verify
  ledger invariant before arming.
- *SPA catch-all shadows /api or /ws* → API breaks. Mitigation: register the fallback last,
  exclude `/api` and `/ws` prefixes; covered by an offline test.
- *Redirect URL / IP not updated in Kite* → login or order routes fail. Mitigation: explicit
  owner checklist step, verified before arming.
- *Single-disk data loss* → lose P&L history. Mitigation: nightly SQLite backup + DO snapshots.

## Owner action checklist (things Claude cannot do)
1. Create the droplet (DO → Bangalore BLR1, Ubuntu 24.04, ~$6/mo, add SSH key); share the IP.
2. Generate a Tailscale one-off auth key; approve the new machine.
3. Kite console: whitelist droplet IP + set redirect URL to the tailnet `/api/session`.
4. Place secrets into `backend/.env` on the droplet (template + secure copy provided).
5. Daily Kite re-auth via the Connect Kite button (unchanged).

## Success criteria
- Backend runs under systemd, survives reboot (comes up disarmed), Mac can be off.
- Phone reaches `https://paper-trader.<tailnet>.ts.net` from any network; UI + live WS work.
- Kite login completes end-to-end from the phone; order routes accept the droplet IP.
- Ledger invariant holds on the droplet after cutover.
- Exactly one live engine against the account at all times.
