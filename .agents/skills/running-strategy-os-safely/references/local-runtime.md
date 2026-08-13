# Local runtime procedure

From `paper-trader/backend`, create a unique temporary database path and run:

```bash
PT_DISABLE_DOTENV=1 PT_PROVIDER=mock PT_EXECUTION=paper PT_LIVE_ACK= \
PT_DB_PATH=/tmp/strategyos-local-<unique>.db \
.venv/bin/uvicorn app.main:app --port 8090
```

Wait for `/api/health` to report ready with mock provider, paper mode, unarmed state, and both expected loops. From `paper-trader/frontend`, run the development server on port 5173 and use it as the SPA endpoint. A backend `GET /` 404 in this dev arrangement is expected when the SPA is served by Vite.

Do not use `timeout` on macOS. Keep process IDs, stop them on completion, and remove only the unique temporary database you created.
