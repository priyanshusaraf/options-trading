"""Re-fetch incomplete instrument-years month by month (slow, polite)."""
import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
DATA_ROOT = _os.environ.get("COMMODITY_DATA", _os.path.join(HERE, "data"))
import os, subprocess, time, glob, calendar
import pandas as pd
D = DATA_ROOT
BIN = f"{D}/tool/node_modules/.bin/dukascopy-node"
MIN_ROWS = {"gascmdusd": 60000, "lightcmdusd": 60000, "xauusd": 62000, "xagusd": 62000}
for _pass in range(3):
  for inst in ("xauusd", "xagusd", "lightcmdusd", "gascmdusd"):
      for y in range(2019, 2027):
          f = f"{D}/raw/{inst}/{inst}_{y}.csv"
          n = sum(1 for _ in open(f)) - 1 if os.path.exists(f) else 0
          need = MIN_ROWS[inst] if y < 2026 else MIN_ROWS[inst] * 0.74
          if n >= need:
              continue
          print(inst, y, "has", n, "-> refetch monthly", flush=True)
          parts = [pd.read_csv(f)] if n > 0 else []   # keep what the yearly file already had
          last_m = 9 if y == 2026 else 12
          for m in range(1, last_m + 1):
              frm = f"{y}-{m:02d}-01"
              to = f"{y+1}-01-01" if m == 12 else f"{y}-{m+1:02d}-01"
              if y == 2026 and m == 9:
                  to = "2026-10-07"
              fn = f"{inst}_{y}_{m:02d}"
              out = f"{D}/rawm/{inst}/{fn}.csv"
              for attempt in range(6):
                  if os.path.exists(out) and os.path.getsize(out) > 1000:
                      break
                  subprocess.run([BIN, "-i", inst, "-from", frm, "-to", to, "-t", "m5", "-f", "csv",
                                  "-v", "true", "-dir", f"{D}/rawm/{inst}", "-fn", fn,
                                  "-r", "5", "-rp", "3000", "-bs", "2", "-bp", "3000"],
                                 capture_output=True)
                  if os.path.exists(out) and os.path.getsize(out) > 1000:
                      break
                  time.sleep(20 * (attempt + 1))
              try:
                  if os.path.exists(out) and os.path.getsize(out) > 1000:
                      parts.append(pd.read_csv(out))
                  else:
                      print("  month failed", inst, y, m, flush=True)
                      if os.path.exists(out):
                          os.remove(out)
              except Exception as e:
                  print("  month unreadable", inst, y, m, e, flush=True)
              time.sleep(3)
          if parts:
              df = pd.concat(parts).drop_duplicates("timestamp").sort_values("timestamp")
              df.to_csv(f, index=False)
              print(inst, y, "now", len(df), flush=True)
print("REFETCH PASS DONE")
