"""Refresh the intraday (MIS) ineligibility blocklist from the owner's Google Sheet.

The sheet (gid 288818195) is the FULL MIS margin table — every stock with its
`MIS Multiplier` (the intraday leverage Zerodha allows). A name is blocked from the
bot's intraday/equity_intraday portfolio when its multiplier is BELOW
`--min-multiplier`, because the bot sizes intraday at 5x and an order that needs more
leverage than the stock allows gets rejected / under-margined.

  --min-multiplier 2  (default) -> blocks 1x names + blank/#N/A rows  (the owner's
                                   "multiplier == 1 or blank" rule)
  --min-multiplier 5            -> also blocks 2x/3x/4x names that can't take the
                                   bot's 5x sizing  (recommended once confirmed)

Re-run any time to refresh:  .venv/bin/python scripts/fetch_mis_blocklist.py
Writes app/data/mis_blocklist.json (the engine loads it; never hand-edit the names).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import urllib.request

SHEET_ID = "1fLTsNpFJPK349RTjs0GRSXJZD-5soCUkZt9eSMTJ2m4"
GID = "288818195"
URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
OUT = os.path.join(os.path.dirname(__file__), "..", "app", "data", "mis_blocklist.json")


def fetch_rows():
    with urllib.request.urlopen(URL, timeout=30) as resp:   # follows Google's redirect
        text = resp.read().decode("utf-8", "replace")
    rdr = csv.reader(io.StringIO(text))
    next(rdr)                                  # drop the group-label super-header row
    header = [h.strip() for h in next(rdr)]    # the REAL header is row 2
    return header, [dict(zip(header, row)) for row in rdr]


def build_blocklist(rows, header, min_multiplier: float) -> set[str]:
    sym_c = next(h for h in header if h.lower() == "symbol")
    mul_c = next(h for h in header if "mis" in h.lower() and "mult" in h.lower())
    blocked: set[str] = set()
    for r in rows:
        sym = (r.get(sym_c) or "").strip().upper()
        if not sym or sym == "SYMBOL":         # skip blanks / the stray header-ish row
            continue
        raw = (r.get(mul_c) or "").strip().lower().rstrip("x")
        try:
            mult = float(raw)
        except ValueError:
            blocked.add(sym)                   # blank / #N/A / garbage -> block (conservative)
            continue
        if mult < min_multiplier:
            blocked.add(sym)
    return blocked


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-multiplier", type=float, default=2.0,
                    help="block names whose MIS multiplier is BELOW this (default 2 = 1x + blank)")
    args = ap.parse_args()
    header, rows = fetch_rows()
    blocked = build_blocklist(rows, header, args.min_multiplier)
    payload = {"min_multiplier": args.min_multiplier, "count": len(blocked),
               "blocked": sorted(blocked), "source": URL}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=1)
        f.write("\n")
    print(f"wrote {len(blocked)} blocked symbols (multiplier < {args.min_multiplier}) "
          f"-> {os.path.relpath(OUT)}")
    print("blocked:", sorted(blocked))


if __name__ == "__main__":
    main()
