"""
Flask backend. Holds the Kite session, runs the strategy math, serves the UI.

Run:
    pip install -r requirements.txt
    python server.py
then open http://127.0.0.1:5000
"""
import os
import pandas as pd
from flask import Flask, jsonify, request, redirect, send_from_directory

from config import API_KEY, API_SECRET, UNDERLYINGS, DEFAULTS, INTERVALS
from kite_client import KiteClient
from strategy import compute_signals, to_payload

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "frontend")
app = Flask(__name__, static_folder=None)
client = KiteClient(API_KEY, API_SECRET)


# ---- static / pages -------------------------------------------------------
@app.get("/")
def index():
    return send_from_directory(FRONTEND, "index.html")


@app.get("/<path:path>")
def assets(path):
    return send_from_directory(FRONTEND, path)


# ---- auth -----------------------------------------------------------------
@app.get("/api/status")
def status():
    return jsonify({
        "authenticated": client.is_authenticated(),
        "login_url": client.login_url(),
        "has_credentials": bool(API_KEY and API_SECRET),
    })


@app.get("/api/session")
def session():
    """Kite OAuth redirects here with ?request_token=... after login."""
    rt = request.args.get("request_token")
    if not rt:
        return "Missing request_token", 400
    try:
        client.complete_session(rt)
    except Exception as e:
        return f"Login failed: {e}", 400
    return redirect("/")


# ---- metadata -------------------------------------------------------------
@app.get("/api/meta")
def meta():
    return jsonify({
        "underlyings": list(UNDERLYINGS.keys()),
        "intervals": INTERVALS,
        "defaults": DEFAULTS,
    })


# ---- data -----------------------------------------------------------------
def _require_auth():
    if not client.is_authenticated():
        return jsonify({"error": "Not connected to Kite. Click Connect."}), 401
    return None


@app.get("/api/ltp")
def ltp():
    guard = _require_auth()
    if guard:
        return guard
    name = request.args.get("underlying", "NIFTY 50")
    cfg = UNDERLYINGS.get(name)
    if not cfg:
        return jsonify({"error": f"Unknown underlying {name}"}), 400
    try:
        return jsonify({"underlying": name, "last_price": client.ltp(cfg["ltp_symbol"])})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.get("/api/candles")
def candles():
    guard = _require_auth()
    if guard:
        return guard
    name = request.args.get("underlying", "NIFTY 50")
    interval = request.args.get("interval", DEFAULTS["interval"])
    cfg = UNDERLYINGS.get(name)
    if not cfg:
        return jsonify({"error": f"Unknown underlying {name}"}), 400
    try:
        token = client.resolve_token(cfg["ltp_symbol"], cfg["token"])
        raw = client.candles(token, interval, DEFAULTS["days"])
        df = pd.DataFrame(raw)
        if df.empty:
            return jsonify({"error": "No candles returned."}), 404
        df = df.iloc[:-1].reset_index(drop=True)        # drop the still-forming bar
        sig = compute_signals(
            df,
            ema_length=DEFAULTS["ema_length"],
            z_length=DEFAULTS["z_length"],
            entry_z=DEFAULTS["entry_z"],
            slope_lookback=DEFAULTS["slope_lookback"],
        )
        payload = to_payload(sig, entry_z=DEFAULTS["entry_z"])
        payload["underlying"] = name
        payload["interval"] = interval
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
