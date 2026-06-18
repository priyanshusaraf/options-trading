#!/usr/bin/env bash
set -euo pipefail

echo "════════════════════════════════════════════"
echo "  Stock Market Intelligence Platform Setup  "
echo "════════════════════════════════════════════"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# ── Python virtualenv ──────────────────────────────────────────────────────────
echo ""
echo "▶ Setting up Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r backend/requirements.txt -q
echo "  ✓ Python dependencies installed"

# ── .env file ─────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  ✓ Created .env from template — edit it with your API keys"
else
  echo "  ✓ .env already exists"
fi

# ── Data directories ───────────────────────────────────────────────────────────
mkdir -p data/{parquet/1d,parquet/1wk,sqlite,reports,cache,logs}
echo "  ✓ Data directories created"

# ── Frontend ───────────────────────────────────────────────────────────────────
echo ""
echo "▶ Setting up frontend..."
cd frontend
if [ ! -f .env ]; then
  cp .env.example .env
fi
npm install -q
echo "  ✓ Frontend dependencies installed"
cd ..

echo ""
echo "════════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Edit .env with your API keys (at minimum, nothing is required)"
echo "  2. Run: ./scripts/start.sh"
echo "════════════════════════════════════════════"
