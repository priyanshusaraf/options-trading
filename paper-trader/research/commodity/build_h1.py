"""Build MCX-session 60m bars (IST :30-aligned) from Dukascopy hourly csv(s)."""
import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
DATA_ROOT = _os.environ.get("COMMODITY_DATA", _os.path.join(HERE, "data"))
import glob, sys
import pandas as pd
sys.path.insert(0, HERE)
from build_dataset import usdinr, SPECS, D, OUT
sym = sys.argv[1]
name, factor, _ = SPECS[sym]
files = sorted(glob.glob(f"{D}/h1/{sym}_h1*.csv"))
df = pd.concat([pd.read_csv(f) for f in files]).drop_duplicates("timestamp").sort_values("timestamp")
df.index = pd.to_datetime(df.timestamp, unit="ms") + pd.Timedelta(hours=5, minutes=30)
df = df[["open", "high", "low", "close", "volume"]]
df = df[~((df.high == df.low) & (df.volume == 0))]
from build_dataset import fx_rate
rate = fx_rate(df.index)
for c in ("open", "high", "low", "close"):
    df[c] = df[c].to_numpy() * rate * factor
mins = df.index.hour * 60 + df.index.minute
df = df[(df.index.weekday < 5) & (mins >= 9 * 60 + 30) & (mins <= 22 * 60 + 30)]
df.index.name = "date"
df.to_pickle(f"{OUT}/{name}_60m.pkl")
print(name, len(df), df.index.min(), df.index.max(), round(df.close.iloc[0], 1), round(df.close.iloc[-1], 1))
print(df.groupby(df.index.year).size().to_dict())
