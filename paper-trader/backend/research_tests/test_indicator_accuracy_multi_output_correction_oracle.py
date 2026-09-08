"""Independent specification oracle, authored before product/prior oracle inspection.

Exact binary64 observations are rational reals. All rational operations stay exact;
only square roots use a private Decimal context. No Strategy OS imports are allowed.
"""
from collections import deque
from decimal import Decimal, localcontext
from fractions import Fraction as Q
import math

PORTS = {
    "BOLLINGER_BANDS": ("lower", "middle", "upper"),
    "BOLLINGER_BANDWIDTH": ("value",), "BOLLINGER_PERCENT_B": ("value",),
    "DONCHIAN_CHANNELS": ("lower", "middle", "upper"),
    "KELTNER_CHANNELS": ("lower", "middle", "upper"),
    "MACD": ("macd", "signal", "histogram"), "PPO": ("value",),
    "STOCHASTIC": ("k", "d"), "STOCH_RSI": ("k", "d"),
}
DEFAULTS = {
    **{n: {"window": 14, "deviations": 2} for n in
       ("BOLLINGER_BANDS", "BOLLINGER_BANDWIDTH", "BOLLINGER_PERCENT_B")},
    "DONCHIAN_CHANNELS": {"window": 14},
    "KELTNER_CHANNELS": {"window": 14, "atr_length": 14, "multiplier": 2, "basis_type": "EMA"},
    "MACD": {"fast_length": 12, "slow_length": 26, "signal_length": 9, "source": "close"},
    "PPO": {"fast_length": 12, "slow_length": 26, "moving_average_type": "EMA"},
    "STOCHASTIC": {"k_length": 14, "k_smoothing": 3, "d_smoothing": 3},
    "STOCH_RSI": {"rsi_length": 14, "stochastic_length": 14, "k_smoothing": 3, "d_smoothing": 3},
}


def lookback(name, p):
    if name.startswith("BOLLINGER") or name == "DONCHIAN_CHANNELS": return p["window"] - 1
    if name == "KELTNER_CHANNELS": return max(p["window"] - 1, p["atr_length"])
    if name == "MACD": return p["slow_length"] + p["signal_length"] - 2
    if name == "PPO": return p["slow_length"] - 1
    if name == "STOCHASTIC": return p["k_length"] + p["k_smoothing"] + p["d_smoothing"] - 3
    return p["rsi_length"] + p["stochastic_length"] + p["k_smoothing"] + p["d_smoothing"] - 3


def selected_fields(name, p):
    if name == "DONCHIAN_CHANNELS": return ["high", "low"]
    if name in ("KELTNER_CHANNELS", "STOCHASTIC"): return ["high", "low", "close"]
    if name == "MACD":
        return {"hl2": ["high", "low"], "hlc3": ["high", "low", "close"],
                "ohlc4": ["open", "high", "low", "close"]}.get(p["source"], [p["source"]])
    return ["close"]


def mean(values): return sum(values, Q(0)) / len(values)


def sma(xs, n):
    result = []; window = deque(); total = Q(0)
    for x in xs:
        if x is None: window.clear(); total = Q(0); result.append(None); continue
        window.append(x); total += x
        if len(window) > n: total -= window.popleft()
        result.append(total / n if len(window) == n else None)
    return result


def ema(xs, n, alpha=None):
    alpha = Q(2, n + 1) if alpha is None else alpha
    result = []; seed = []; value = None
    for x in xs:
        if x is None: seed = []; value = None; result.append(None); continue
        if value is None:
            seed.append(x)
            if len(seed) == n: value = mean(seed)
        else: value += alpha * (x - value)
        result.append(value)
    return result


def decimal(x): return Decimal(x.numerator) / Decimal(x.denominator)


def finite_float(x):
    if x is None: return None
    try: value = float(x)
    except OverflowError: return None
    return value if math.isfinite(value) else None


def segment(name, p, rows):
    """Evaluate one independently valid contiguous segment using the frozen spec."""
    size = len(next(iter(rows.values()))); close = rows.get("close")
    out = {port: [None] * size for port in PORTS[name]}
    if name.startswith("BOLLINGER"):
        n = p["window"]; means = sma(close, n); squares = sma([x*x for x in close], n)
        for i in range(n - 1, size):
            m = means[i]; variance = squares[i] - m*m
            with localcontext() as ctx:
                ctx.prec = 120
                spread = decimal(variance).sqrt() * decimal(Q(p["deviations"]))
                middle = decimal(m); low = middle-spread; high = middle+spread
                if name == "BOLLINGER_BANDS":
                    for key,value in zip(PORTS[name],(low,middle,high)):out[key][i]=finite_float(value)
                elif name == "BOLLINGER_BANDWIDTH":
                    out["value"][i]=finite_float(200*spread/middle) if m else None
                else:
                    out["value"][i]=finite_float((decimal(close[i])-low)/(2*spread)) if spread else None
    elif name == "DONCHIAN_CHANNELS":
        for i in range(p["window"]-1,size):
            left=i+1-p["window"]; low=min(rows["low"][left:i+1]); high=max(rows["high"][left:i+1])
            for key,value in zip(PORTS[name],(low,(low+high)/2,high)):out[key][i]=finite_float(value)
    elif name == "KELTNER_CHANNELS":
        basis=(ema if p["basis_type"]=="EMA" else sma)(close,p["window"])
        tr=[None]+[max(rows["high"][i]-rows["low"][i],abs(rows["high"][i]-close[i-1]),abs(rows["low"][i]-close[i-1])) for i in range(1,size)]
        atr=ema(tr,p["atr_length"],Q(1,p["atr_length"]))
        for i in range(lookback(name,p),size):
            spread=Q(p["multiplier"])*atr[i]; m=basis[i]
            for key,value in zip(PORTS[name],(m-spread,m,m+spread)):out[key][i]=finite_float(value)
    elif name == "MACD":
        fields=selected_fields(name,p); src=[mean([rows[f][i] for f in fields]) for i in range(size)]
        slow=p["slow_length"];fast=p["fast_length"];differences=[None]*size
        if size>=slow:
            a=mean(src[slow-fast:slow]);b=mean(src[:slow]);differences[slow-1]=a-b
            for i in range(slow,size):
                a+=Q(2,fast+1)*(src[i]-a);b+=Q(2,slow+1)*(src[i]-b);differences[i]=a-b
        sig=ema(differences,p["signal_length"])
        for i in range(lookback(name,p),size):
            for key,value in zip(PORTS[name],(differences[i],sig[i],differences[i]-sig[i])):out[key][i]=finite_float(value)
    elif name == "PPO":
        ma=ema if p["moving_average_type"]=="EMA" else sma
        fast=ma(close,p["fast_length"]);slow=ma(close,p["slow_length"])
        for i in range(p["slow_length"]-1,size):out["value"][i]=finite_float(100*(fast[i]-slow[i])/slow[i]) if slow[i] else None
    else:
        if name == "STOCHASTIC":
            raw=[None]*size;n=p["k_length"]
            for i in range(n-1,size):
                lo=min(rows["low"][i+1-n:i+1]);hi=max(rows["high"][i+1-n:i+1])
                raw[i]=100*(close[i]-lo)/(hi-lo) if hi!=lo else Q(0)
        else:
            delta=[None]+[close[i]-close[i-1] for i in range(1,size)]
            n=p["rsi_length"];gain=ema([max(x,Q(0)) if x is not None else None for x in delta],n,Q(1,n))
            loss=ema([max(-x,Q(0)) if x is not None else None for x in delta],n,Q(1,n))
            rsi=[None if g is None else 100*g/(g+l) if g+l else Q(0) for g,l in zip(gain,loss)]
            raw=[None]*size;w=p["stochastic_length"]
            for i in range(n+w-1,size):
                block=rsi[i+1-w:i+1];lo=min(block);hi=max(block)
                raw[i]=100*(rsi[i]-lo)/(hi-lo) if hi!=lo else Q(0)
        k=sma(raw,p["k_smoothing"]);d=sma(k,p["d_smoothing"])
        for i in range(lookback(name,p),size):out['k'][i]=finite_float(k[i]);out['d'][i]=finite_float(d[i])
    return out


def expected(name, p, data):
    """Reset on missing/nonfinite required fields; preserve every original row."""
    fields=selected_fields(name,p); size=len(data[fields[0]])
    result={port:[None]*size for port in PORTS[name]};start=0
    for i in range(size+1):
        good=i<size and all(data[f][i] is not None and math.isfinite(float(data[f][i])) for f in fields)
        if good: continue
        if i>start:
            block={f:[Q(float(x)) for x in data[f][start:i]] for f in fields}
            values=segment(name,p,block)
            for port in result:result[port][start:i]=values[port]
        start=i+1
    return result


def test_exact_constant_ratio_does_not_create_stochastic_movement():
    p=DEFAULTS['STOCH_RSI']; values=[100.0]*240;values[50]=101.0
    result=expected('STOCH_RSI',p,{'close':values})
    assert result['k'][100:]==[0.0]*140
    assert result['d'][100:]==[0.0]*140


def test_oracle_named_ports_and_exact_constant_bands():
    assert sum(map(len,PORTS.values()))==19
    result=expected('BOLLINGER_BANDS',DEFAULTS['BOLLINGER_BANDS'],{'close':[7.0]*20})
    assert all(v[:13]==[None]*13 and v[13:]==[7.0]*7 for v in result.values())
