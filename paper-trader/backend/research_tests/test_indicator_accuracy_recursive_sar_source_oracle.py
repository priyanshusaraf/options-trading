"""Exact rational expectations, authored before corrected implementation inspection.

Authority: immutable semantic-contracts.md plus SAR decision.json
4d5d654326d8665fc94f44aaf08736305d59843e2cd9ecbd726de143ebec5e0e;
TA_SAR ordering at 2247d599bddf37ed37e3a709371517e46efc66f6.
Binary64 observations and SAR factors are interpreted as exact real numbers.
The original independent oracle supplies only declared domains and input fixtures.
"""
from fractions import Fraction as Q
import math
from research_tests import test_indicator_accuracy_recursive_state_oracle as original

NAMES = original.NAMES
FIELDS = original.FIELDS
PARAMS = original.PARAMS

def q(x):
    return Q.from_float(float(x))

def finite_float(x):
    if x is None:
        return None
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except OverflowError:
        return None

def rational_segment(name, rows, p, trace=None):
    """Unrounded recurrence; no chosen decimal precision can erase cancellation."""
    d = [{k:q(v) for k,v in r.items()} for r in rows]
    result = [None] * len(d)
    w = p.get('window', 0)
    ma = None
    acc = Q(0)
    pos = neg = trsum = Q(0)
    gains = losses = ranges = Q(0)
    dxsum = Q(0)
    adx = None
    poisoned = False
    nearzero = lambda x: abs(x) < q(1e-14)
    for i,r in enumerate(d):
        c = r['close']
        prev = d[i-1] if i else None
        y = None
        if name in ('EMA','RMA_WILDER','MA_SLOPE','PRICE_MA_DISTANCE'):
            old = ma
            if i == w-1:
                ma = sum(z['close'] for z in d[:w]) / w
            elif i >= w:
                a = Q(1,w) if name == 'RMA_WILDER' else Q(2,w+1)
                ma = (1-a)*ma + a*c
            if ma is not None:
                y = c-ma if name == 'PRICE_MA_DISTANCE' else (ma-old if old is not None else None) if name == 'MA_SLOPE' else ma
        elif name in ('ACCUMULATION_DISTRIBUTION','CHAIKIN_OSCILLATOR'):
            width = r['high']-r['low']
            acc += (2*c-r['high']-r['low'])*r['volume']/width if width else 0
            if name == 'ACCUMULATION_DISTRIBUTION':
                y = acc
            else:
                if i == 0:
                    fast = slow = acc
                else:
                    a,b = Q(2,p['fast_length']+1),Q(2,p['slow_length']+1)
                    fast,slow = (1-a)*fast+a*acc,(1-b)*slow+b*acc
                if i >= p['slow_length']-1:
                    y = fast-slow
        elif name == 'CUMULATIVE_RETURN':
            y = c/d[0]['close']-1 if d[0]['close'] else None
        elif name == 'OBV':
            if not i: acc = r['volume']
            elif c != prev['close']: acc += r['volume'] if c > prev['close'] else -r['volume']
            y = acc
        elif name == 'PRICE_VOLUME_TREND':
            if i and not prev['close']: poisoned = True
            if i and not poisoned: acc += (c-prev['close'])*r['volume']/prev['close']
            y = None if poisoned else acc
        elif name == 'KAMA':
            if i >= w:
                path = sum(abs(d[j]['close']-d[j-1]['close']) for j in range(i-w+1,i+1))
                er = abs(c-d[i-w]['close'])/path if path else Q(1)
                a = (er*(Q(2,p['fast_length']+1)-Q(2,p['slow_length']+1))+Q(2,p['slow_length']+1))**2
                if i == w: ma = prev['close']
                ma = (1-a)*ma+a*c
                y = ma
        elif name in ('ATR','NATR','RSI','PLUS_DI','MINUS_DI','ADX'):
            if i:
                tr = max(r['high']-r['low'],abs(r['high']-prev['close']),abs(r['low']-prev['close']))
                if name in ('ATR','NATR','RSI'):
                    change = c-prev['close']
                    gain,loss = max(Q(0),change),max(Q(0),-change)
                    if i <= w:
                        ranges += tr; gains += gain; losses += loss
                        if i == w: ranges /= w; gains /= w; losses /= w
                    else:
                        ranges = (ranges*(w-1)+tr)/w
                        gains = (gains*(w-1)+gain)/w
                        losses = (losses*(w-1)+loss)/w
                    if i >= w:
                        y = (100*gains/(gains+losses) if gains+losses else Q(0)) if name == 'RSI' else (100*ranges/c if c else None) if name == 'NATR' else ranges
                else:
                    up,down = r['high']-prev['high'],prev['low']-r['low']
                    a,b = (up if up > max(0,down) else Q(0)),(down if down > max(0,up) else Q(0))
                    if i < w: pos += a; neg += b; trsum += tr
                    else:
                        pos = pos*(w-1)/w+a; neg = neg*(w-1)/w+b; trsum = trsum*(w-1)/w+tr
                        pi,mi = (Q(0),Q(0)) if nearzero(trsum) else (100*pos/trsum,100*neg/trsum)
                        dx = None if nearzero(trsum) or nearzero(pi+mi) else 100*abs(pi-mi)/(pi+mi)
                        if name == 'PLUS_DI': y = pi
                        elif name == 'MINUS_DI': y = mi
                        else:
                            if i <= 2*w-1: dxsum += dx if dx is not None else 0
                            if i == 2*w-1: adx = dxsum/w
                            elif i > 2*w-1 and dx is not None: adx = (adx*(w-1)+dx)/w
                            y = adx
        elif name == 'PARABOLIC_SAR':
            if i:
                if i == 1:
                    up,down = r['high']-prev['high'],prev['low']-r['low']
                    direction = -1 if down > 0 and down > up else 1
                    ep = r['high'] if direction == 1 else r['low']
                    stop = prev['low'] if direction == 1 else prev['high']
                    af = q(p['start'])
                prior = r if i == 1 else prev
                reversed_now = r['low'] <= stop if direction == 1 else r['high'] >= stop
                if reversed_now:
                    direction *= -1
                    stop = min(ep,prior['low'],r['low']) if direction == 1 else max(ep,prior['high'],r['high'])
                    ep = r['high'] if direction == 1 else r['low']
                    af = q(p['start'])
                elif (direction == 1 and r['high'] > ep) or (direction == -1 and r['low'] < ep):
                    ep = r['high'] if direction == 1 else r['low']
                    af = min(q(p['maximum']),af+q(p['increment']))
                y = stop
                projected = (1-af)*stop+af*ep
                stop = min(projected,prior['low'],r['low']) if direction == 1 else max(projected,prior['high'],r['high'])
                if trace is not None:
                    trace.append(dict(i=i,direction=direction,reversal=reversed_now,af=af,ep=ep,value=y,next_sar=stop,clamped=stop != projected))
        else:
            raise AssertionError(name)
        result[i] = y
    return result

def exact(name, rows, p, breaks=()):
    out = [None]*len(rows)
    start = 0
    def flush(end):
        if end > start: out[start:end] = rational_segment(name,rows[start:end],p)
    for i,r in enumerate(rows):
        good = all(k in r and math.isfinite(r[k]) for k in FIELDS[name])
        if good and 'high' in FIELDS[name]: good = r['high'] >= r['low']
        if good and 'volume' in FIELDS[name]: good = r['volume'] >= 0
        if i in breaks: flush(i); start = i
        if not good: flush(i); start = i+1
    flush(len(rows))
    return out

def expected(name,rows,p,breaks=()):
    return [finite_float(x) for x in exact(name,rows,p,breaks)]

def cases():
    for name in NAMES:
        for kind in ('mixed','tiny','offset','zero','flat','nonfinite','invalid_range','negative_volume','zero_close'):
            yield dict(id=f'exact-{name}-{kind}',name=name,parameters=original.parameters(name),rows=original.fixture(kind,64))
    for start,increment,maximum in [(0,0,0),(1,1,1),(.03,.07,.4),(0,.1,.2),(.2,0,.2),(.02,.02,.2)]:
        for kind in ('mixed','ties','ramp','large','offset','tiny'):
            yield dict(id=f'exact-SAR-{start}-{increment}-{maximum}-{kind}',name='PARABOLIC_SAR',parameters=dict(start=start,increment=increment,maximum=maximum),rows=original.fixture(kind,96))
    for constant in [math.nextafter(0.,1.),1e-300,1e300,float.fromhex('0x1.fffffffffffffp+1023')]:
        for name in NAMES:
            rows=[dict(close=constant,high=constant,low=constant,volume=constant) for _ in range(40)]
            yield dict(id=f'exact-{name}-constant-{constant.hex()}',name=name,parameters=original.parameters(name),rows=rows)
    # Exact cancellation with all finite inputs; adjacent binary64 extremes and
    # opposite-sign observations distinguish loss of a small residual from zero.
    for name in NAMES:
        rows=[]
        for i in range(50):
            c=[2.**900,-2.**900,2.**-900,2.**900,-2.**900][i%5]
            rows.append(dict(close=c,high=max(c,0.),low=min(c,0.),volume=1.))
        yield dict(id=f'exact-{name}-cancellation',name=name,parameters=original.parameters(name,'minimum'),rows=rows)

def test_exact_arithmetic_crosschecks():
    rows=[dict(close=float(c),high=float(c+1),low=float(c-1),volume=10.) for c in [2,4,3,6]]
    assert exact('EMA',rows,{'window':2}) == [None,Q(3),Q(3),Q(5)]
    assert exact('RMA_WILDER',rows,{'window':2}) == [None,Q(3),Q(3),Q(9,2)]
    assert exact('ATR',rows,{'window':2}) == [None,None,Q(5,2),Q(13,4)]
    assert exact('PRICE_VOLUME_TREND',rows,{}) == [0,10,Q(15,2),Q(35,2)]
    # Constant recurrences must satisfy their algebraic fixed points exactly,
    # including subnormal observations that require >1000 decimal places.
    for value in [math.nextafter(0.,1.),1e-300,1e300,float.fromhex('0x1.fffffffffffffp+1023')]:
        rows=[dict(close=value,high=value,low=value,volume=value) for _ in range(40)]
        for name in NAMES:
            p=original.parameters(name)
            out=exact(name,rows,p)
            target=q(value) if name in ('EMA','RMA_WILDER','KAMA','OBV','PARABOLIC_SAR') else Q(0)
            assert out[original.first_valid(name,p):] == [target]*(40-original.first_valid(name,p)),name
    # Finite cancellation has an exact nonzero seed, not rounded zero.
    rows=[dict(close=x,high=max(x,0),low=min(x,0),volume=1.) for x in [2.**900,2.**-900,-2.**900]]
    assert exact('EMA',rows,{'window':3})[-1] == Q(1,3*2**900)
