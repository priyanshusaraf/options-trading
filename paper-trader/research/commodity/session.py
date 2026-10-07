import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
DATA_ROOT = _os.environ.get("COMMODITY_DATA", _os.path.join(HERE, "data"))
import sys, numpy as np, pandas as pd
D = _os.path.join(DATA_ROOT, "mcx")
name = sys.argv[1]
df = pd.read_pickle(f"{D}/{name}_15m.pkl")
ny = df.index.tz_localize("Asia/Kolkata").tz_convert("America/New_York")
df["dst"] = [bool(t.dst()) for t in ny]
df["hm"] = df.index.hour * 60 + df.index.minute
rows = []
for d, g in df.groupby(df.index.date):
    if len(g) < 40: continue
    dst = g.dst.iloc[0]
    us = 18 * 60 + 30 if dst else 19 * 60 + 30     # 09:00 ET in IST
    pre = g[g.hm < us]; post = g[g.hm >= us]
    if len(pre) < 20 or len(post) < 8: continue
    o = g.open.iloc[0]
    p_close = pre.close.iloc[-1]
    first_h = post.iloc[:4]
    r_pre = p_close / o - 1
    r_fh = first_h.close.iloc[-1] / first_h.open.iloc[0] - 1
    r_rest = post.close.iloc[-1] / first_h.close.iloc[-1] - 1
    r_post = post.close.iloc[-1] / post.open.iloc[0] - 1
    # previous day
    rows.append(dict(d=pd.Timestamp(d), r_pre=r_pre, r_fh=r_fh, r_rest=r_rest, r_post=r_post,
                     r_day=g.close.iloc[-1] / o - 1,
                     pre_rng=(pre.high.max() - pre.low.min()) / o,
                     brk_up=post.high.max() > pre.high.max(), brk_dn=post.low.min() < pre.low.min()))
s = pd.DataFrame(rows).set_index("d")
s["r_prev"] = s.r_day.shift(1)
for per, g in (("IS", s[s.index < "2024"]), ("OOS", s[s.index >= "2024"])):
    print(per, len(g))
    for a, b in (("r_pre", "r_post"), ("r_fh", "r_rest"), ("r_prev", "r_day"), ("r_pre", "r_rest"), ("r_prev", "r_post")):
        c = g[a].corr(g[b])
        # sign strategy: trade b in the direction of a
        pnl = np.sign(g[a]) * g[b] * 1e4
        print(f"  corr({a},{b})={c:+.3f}  sign-follow mean={pnl.mean():+.1f}bps t={pnl.mean()/pnl.std()*np.sqrt(len(pnl)):+.2f}")
    # pre-range quantile vs post abs move
    q = pd.qcut(g.pre_rng, 5, labels=False)
    print("  pre-range quintile -> mean |r_post| bps:", (g.r_post.abs() * 1e4).groupby(q).mean().round(0).tolist())
