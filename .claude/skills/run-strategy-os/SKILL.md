---
name: run-strategy-os
description: Start the Strategy OS backend and frontend locally for real runtime verification, safely — mock provider, paper mode, temporary database, never the live ledger or a real broker session. Use whenever UI or end-to-end behaviour must actually be observed.
---

# Run Strategy OS locally

## Safety first — this is not optional

The production bot runs 24/7 on a Bangalore VPS and holds real positions. A local instance must
never contend with it or touch its state.

- **Never** start a local instance with the shipped `.env`: it satisfies all three live gates
  (`PT_EXECUTION=live`, `PT_LIVE_ACK`, `PT_PROVIDER=kite`).
- **Always** force `PT_PROVIDER=mock`, `PT_EXECUTION=paper`, an empty `PT_LIVE_ACK`,
  `PT_DISABLE_DOTENV=1`, and a **temporary** `PT_DB_PATH`.
- Never ARM a local instance.
- One live engine only — starting a local engine against the real ledger is an incident, not a test.

## Backend

```bash
cd paper-trader/backend
PT_DISABLE_DOTENV=1 PT_PROVIDER=mock PT_EXECUTION=paper PT_LIVE_ACK= \
PT_DB_PATH=/tmp/strategyos-dev.db \
.venv/bin/uvicorn app.main:app --port 8090
```

Run it in the background. Readiness:

```bash
curl -s localhost:8090/api/health | jq '{ok, status, provider: .provider_name, loops}'
```

`/api/health` is a **readiness** probe — it answers 503 when the DB is unreachable, the engine
loops are stopped, or the fast risk lane is stale. Wait for `ok: true` and both `risk` and
`signal` loops present before driving the UI.

**`GET /` returns 404 in this dev setup, and that is correct** — the SPA is served by Vite on
:5173, and `PT_SERVE_FRONTEND` is unset. The `GET /` check matters on a **deployed** instance,
where a broken SPA mount is invisible from `/api/health` — that is exactly how the `.env` outage
hid. Do not "fix" a dev 404.

Verified 2026-08-08: this procedure starts cleanly, reports `ok: true` with both loops, resolves
`provider: mock`, `armed: false`, and writes only the temp database.

## Frontend

```bash
cd paper-trader/frontend
npm run dev        # :5173, proxies /api and /ws to :8090
```

Open `http://localhost:5173`.

## Notes

- `python` is not on `PATH` — use `.venv/bin/python` / `.venv/bin/uvicorn`.
- **macOS has no `timeout`** — do not wrap commands in it; it exits 127 and looks like a failure
  of the thing you were testing.
- The mock provider serves a synthetic market, so signals and positions appear without Kite.
- Stop both processes when finished; do not leave a stale engine running.

## After it is up

Drive the real flow with `claude-in-chrome` and follow `.claude/skills/ui-acceptance` — console,
network, 390px, screenshot, independent `ui-verifier`.
