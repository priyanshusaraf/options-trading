"""Independent mathematical oracle. Authored from the nine normative sections.

No product imports, pandas rolling/ewm, implementation fixtures or generators.
Decimal arithmetic models the specified mathematics; pinned native arrays are
separate evidence and are never replaced by these mathematical expectations.
"""
from collections import deque
from decimal import Decimal, localcontext
import math

PORTS = {
    'BOLLINGER_BANDS': ('lower','middle','upper'),
    'BOLLINGER_BANDWIDTH': ('value',), 'BOLLINGER_PERCENT_B': ('value',),
    'DONCHIAN_CHANNELS': ('lower','middle','upper'),
    'KELTNER_CHANNELS': ('lower','middle','upper'),
    'MACD': ('histogram','macd','signal'), 'PPO': ('value',),
    'STOCHASTIC': ('d','k'), 'STOCH_RSI': ('d','k'),
}
DEFAULTS = {
    'BOLLINGER_BANDS': {'window':14,'deviations':2},
    'BOLLINGER_BANDWIDTH': {'window':14,'deviations':2},
    'BOLLINGER_PERCENT_B': {'window':14,'deviations':2},
    'DONCHIAN_CHANNELS': {'window':14},
    'KELTNER_CHANNELS': {'window':14,'atr_length':14,'basis_type':'EMA','multiplier':2},
    'MACD': {'fast_length':12,'slow_length':26,'signal_length':9,'source':'close'},
    'PPO': {'fast_length':12,'slow_length':26,'moving_average_type':'EMA'},
    'STOCHASTIC': {'k_length':14,'k_smoothing':3,'d_smoothing':3},
    'STOCH_RSI': {'rsi_length':14,'stochastic_length':14,'k_smoothing':3,'d_smoothing':3},
}
def fields(component, p):
    if component in ('KELTNER_CHANNELS','STOCHASTIC'): return ('high','low','close')
    if component=='DONCHIAN_CHANNELS': return ('high','low')
    s=p.get('source','close')
    return {'hl2':('high','low'),'hlc3':('high','low','close'),'ohlc4':('open','high','low','close')}.get(s,(s,))

def first_valid(c,p):
    if c.startswith('BOLLINGER') or c=='DONCHIAN_CHANNELS': return p['window']-1
    if c=='KELTNER_CHANNELS': return max(p['window']-1,p['atr_length'])
    if c=='MACD': return p['slow_length']+p['signal_length']-2
    if c=='PPO': return p['slow_length']-1
    if c=='STOCHASTIC': return p['k_length']+p['k_smoothing']+p['d_smoothing']-3
    return p['rsi_length']+p['stochastic_length']+p['k_smoothing']+p['d_smoothing']-3

def rolling(a,n,kind='mean'):
    out=[None]*len(a); q=deque(); s=Decimal(0); ss=Decimal(0)
    for i,x in enumerate(a):
        if x is None: q.clear(); s=ss=Decimal(0); continue
        q.append(x); s+=x; ss+=x*x
        if len(q)>n:
            old=q.popleft(); s-=old; ss-=old*old
        if len(q)==n:
            out[i] = s/n if kind=='mean' else max(Decimal(0),ss/n-(s/n)**2).sqrt()
    return out

def extrema(a,n,maximum):
    q=deque(); count=0; out=[None]*len(a)
    for i,x in enumerate(a):
        if x is None: q.clear(); count=0; continue
        count+=1
        while q and q[0][0]<=i-n: q.popleft()
        while q and ((q[-1][1]<=x) if maximum else (q[-1][1]>=x)): q.pop()
        q.append((i,x))
        if count>=n: out[i]=q[0][1]
    return out

def recurrence(a,n,alpha=None,start=None):
    alpha=Decimal(2)/Decimal(n+1) if alpha is None else alpha
    out=[None]*len(a); seed=[]; state=None
    for i,x in enumerate(a):
        if x is None: seed=[]; state=None; continue
        if start is not None and i<start-n+1: continue
        if state is None:
            seed.append(x)
            if len(seed)<n: continue
            state=sum(seed,Decimal(0))/n
        else: state=state+alpha*(x-state)
        out[i]=state
    return out

def stochastic(h,l,c,n,ks,ds):
    highs=extrema(h,n,True); lows=extrema(l,n,False); raw=[]
    for hi,lo,x in zip(highs,lows,c):
        raw.append(None if hi is None or lo is None or x is None else Decimal(0) if hi==lo else 100*(x-lo)/(hi-lo))
    k=rolling(raw,ks); d=rolling(k,ds)
    return {'k':[x if y is not None else None for x,y in zip(k,d)],'d':d}

def segment(c,p,data):
    count=len(next(iter(data.values()))); x=data.get('close')
    if c.startswith('BOLLINGER'):
        middle=rolling(x,p['window']); std=rolling(x,p['window'],'std'); dev=Decimal.from_float(float(p['deviations']))
        lower=[None if m is None else m-dev*s for m,s in zip(middle,std)]
        upper=[None if m is None else m+dev*s for m,s in zip(middle,std)]
        if c=='BOLLINGER_BANDS': return dict(lower=lower,middle=middle,upper=upper)
        if c=='BOLLINGER_BANDWIDTH': return {'value':[None if m is None or m==0 else 100*(u-l)/m for m,u,l in zip(middle,upper,lower)]}
        return {'value':[None if u is None or u==l else (v-l)/(u-l) for v,u,l in zip(x,upper,lower)]}
    if c=='DONCHIAN_CHANNELS':
        lo=extrema(data['low'],p['window'],False); hi=extrema(data['high'],p['window'],True)
        return dict(lower=lo,upper=hi,middle=[None if a is None else (a+b)/2 for a,b in zip(lo,hi)])
    if c=='KELTNER_CHANNELS':
        basis=rolling(x,p['window']) if p['basis_type']=='SMA' else recurrence(x,p['window'])
        tr=[None]+[max(data['high'][i]-data['low'][i],abs(data['high'][i]-x[i-1]),abs(data['low'][i]-x[i-1])) for i in range(1,count)]
        atr=recurrence(tr,p['atr_length'],Decimal(1)/p['atr_length']); mult=Decimal.from_float(float(p['multiplier']))
        return {'middle':[m if a is not None else None for m,a in zip(basis,atr)],'lower':[None if m is None or a is None else m-mult*a for m,a in zip(basis,atr)],'upper':[None if m is None or a is None else m+mult*a for m,a in zip(basis,atr)]}
    if c in ('MACD','PPO'):
        if c=='MACD': x=[sum(v,Decimal(0))/len(v) for v in zip(*(data[f] for f in fields(c,p)))]
        slow=p['slow_length']; fast=p['fast_length']
        if c=='PPO' and p['moving_average_type']=='SMA': a=rolling(x,fast); b=rolling(x,slow)
        else:
            a=recurrence(x,fast,start=slow-1 if c=='MACD' else None); b=recurrence(x,slow)
        delta=[None if u is None or v is None else u-v for u,v in zip(a,b)]
        if c=='PPO': return {'value':[None if d is None or v==0 else 100*d/v for d,v in zip(delta,b)]}
        signal=recurrence(delta,p['signal_length']); macd=[d if s is not None else None for d,s in zip(delta,signal)]
        return dict(macd=macd,signal=signal,histogram=[None if s is None else d-s for d,s in zip(delta,signal)])
    if c=='STOCHASTIC': return stochastic(data['high'],data['low'],x,p['k_length'],p['k_smoothing'],p['d_smoothing'])
    n=p['rsi_length']; change=[None]+[x[i]-x[i-1] for i in range(1,count)]
    gain=recurrence([None if v is None else max(v,Decimal(0)) for v in change],n,Decimal(1)/n)
    loss=recurrence([None if v is None else max(-v,Decimal(0)) for v in change],n,Decimal(1)/n)
    rsi=[None if g is None else Decimal(0) if g+l==0 else 100*g/(g+l) for g,l in zip(gain,loss)]
    return stochastic(rsi,rsi,rsi,p['stochastic_length'],p['k_smoothing'],p['d_smoothing'])

def oracle(component,parameters,data):
    p=DEFAULTS[component]|parameters; required=fields(component,p); n=len(next(iter(data.values())))
    result={port:[None]*n for port in PORTS[component]}
    valid=[all(data[f][i] is not None and math.isfinite(float(data[f][i])) for f in required) for i in range(n)]
    with localcontext() as ctx:
        ctx.prec=90
        i=0
        while i<n:
            if not valid[i]: i+=1; continue
            j=i+1
            while j<n and valid[j]: j+=1
            block={f:[Decimal.from_float(float(v)) for v in data[f][i:j]] for f in required}
            outputs=segment(component,p,block)
            for port,a in outputs.items(): result[port][i:j]=[None if v is None or not math.isfinite(float(v)) else float(v) for v in a]
            i=j
    return result

def test_oracle_small_hand_values():
    d={'close':[1.,2.,3.,4.],'high':[2.,3.,4.,5.],'low':[0.,1.,2.,3.]}
    b=oracle('BOLLINGER_BANDS',{'window':2,'deviations':2},d)
    assert b=={'lower':[None,.5,1.5,2.5],'middle':[None,1.5,2.5,3.5],'upper':[None,2.5,3.5,4.5]}
    assert oracle('DONCHIAN_CHANNELS',{'window':2},d)['middle']==[None,1.5,2.5,3.5]
    s=oracle('STOCHASTIC',{'k_length':2,'k_smoothing':1,'d_smoothing':1},d)
    assert s['k']==s['d']==[None,200/3,200/3,200/3]
