# Displacement — Strategy Terminal (Phase 1)

A local web terminal that fetches live data from your Kite Connect account,
renders the underlying's price + candlestick chart, and computes your
**Expanding Trend Impulse V3** strategy (EMA50, EMA50 five bars back, slope,
z-score, entry/exit signals) in real time.

**Phase 1 = data + visualization only.** Order execution is wired into the UI
but locked off — it gets enabled in a later phase, after paper trading clears.

## What it shows
- Live underlying price (NIFTY 50 / BANK / FIN SERVICE / SENSEX, or add your own)
- Candlestick chart with the EMA50 overlay and LONG/SHORT entry markers
- A z-score chart with the ±entry thresholds drawn in
- A signal card (LONG ENTRY / SHORT ENTRY / WATCHING / FLAT) for the last closed bar
- A **z-score displacement meter** showing how far price sits from the EMA
- The exact computed values, straight from the same math your Pine uses

## Requirements
- A **paid Kite Connect** subscription (the free Personal plan has no market data)
- Python 3.10+
- Your Kite **API key** and **API secret** from https://developers.kite.trade

## Setup
1. Install dependencies:
   ```
   cd backend
   pip install -r requirements.txt
   ```
2. Provide your Kite credentials — either set environment variables:
   ```
   export KITE_API_KEY=your_key
   export KITE_API_SECRET=your_secret
   ```
   or paste them into `backend/config.py`.
3. In your Kite developer console, set the app's **Redirect URL** to:
   ```
   http://127.0.0.1:5000/api/session
   ```
4. Run it:
   ```
   python server.py
   ```
5. Open http://127.0.0.1:5000 and click **Connect to Kite**. Log in; Kite
   redirects you back and the terminal starts streaming. (The access token
   lasts the trading day; you log in once each morning.)

## How the pieces fit
```
frontend/  ← browser terminal (charts, signal panel, meter)
   │  polls /api/ltp (3s) and /api/candles (20s)
   ▼
backend/server.py   ← Flask: serves UI, holds the Kite session
   ├─ kite_client.py ← auth + candle/LTP fetch from Kite
   └─ strategy.py    ← the Pine port; SINGLE source of truth for the math
```
`strategy.py` is deliberately isolated: backtests, paper trading, the live UI,
and (later) execution all call the same `compute_signals()` so they can never
drift apart.

## Notes
- Times are shown in IST.
- Signals are computed on the **last closed bar** (the forming bar is dropped),
  matching how the strategy fills.
- `strike_step` is already in the config per underlying — that's groundwork for
  the later ATM/ITM/OTM options phase; it does nothing yet.

## Next phases (not built yet)
1. Paper trading on live data + a results view.
2. Options layer: derive ATM/ITM/OTM, pick the contract, factor in IV.
3. Execution: long signal → buy call, short signal → buy put.
