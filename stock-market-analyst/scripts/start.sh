#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Activate virtualenv
source .venv/bin/activate

echo "Starting Stock Market Intelligence Platform..."
echo ""

# Start backend in background
echo "▶ Starting FastAPI backend on http://localhost:8000"
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

sleep 2

# Start frontend in background
echo "▶ Starting React frontend on http://localhost:5173"
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "════════════════════════════════════════════"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  API Docs: http://localhost:8000/docs"
echo "════════════════════════════════════════════"
echo ""
echo "Press Ctrl+C to stop both servers."

# Wait for interrupt
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
