"""Independent 80-digit scalar oracle, authored before product/helper inspection.

Authority: accepted recursive semantic-contracts.md and TA-Lib core
2247d599bddf37ed37e3a709371517e46efc66f6, DEFAULT/unstable=0.
No product import; this file and pre-product expected vectors are immutable receipts.
"""
from decimal import Decimal, localcontext
import math

NAMES = ('ACCUMULATION_DISTRIBUTION','ADX','ATR','CHAIKIN_OSCILLATOR',
         'CUMULATIVE_RETURN','EMA','KAMA','MA_SLOPE','MINUS_DI','NATR','OBV',
         'PARABOLIC_SAR','PLUS_DI','PRICE_MA_DISTANCE','PRICE_VOLUME_TREND','RMA_WILDER','RSI')
FIELDS = {n: ('high','low','close') if n in ('ADX','ATR','MINUS_DI','NATR','PLUS_DI')
          else ('high','low','close','volume') if n in ('ACCUMULATION_DISTRIBUTION','CHAIKIN_OSCILLATOR')
          else ('close','volume') if n in ('OBV','PRICE_VOLUME_TREND')
          else ('high','low') if n=='PARABOLIC_SAR' else ('close',) for n in NAMES}
WINDOW = {'default':14,'minimum':2,'maximum':4096,'type':'exact_integer'}
PARAMS = {n: {'window':dict(WINDOW)} for n in NAMES}
for n in ('ACCUMULATION_DISTRIBUTION','CUMULATIVE_RETURN','OBV','PRICE_VOLUME_TREND'): PARAMS[n]={}
PARAMS['CHAIKIN_OSCILLATOR']={k:dict(WINDOW,default=d) for k,d in [('fast_length',3),('slow_length',10)]}
PARAMS['KAMA'].update(fast_length=dict(WINDOW,minimum=1,default=2),slow_length=dict(WINDOW,default=30))
PARAMS['PARABOLIC_SAR']={k:dict(default=d,minimum=0,maximum=1,type='finite_number') for k,d in [('start',.02),('increment',.02),('maximum',.2)]}
D=lambda x: Decimal.from_float(float(x))
ZERO=Decimal(0)

def parameters(name, point='default'):
    p={k:v[point] for k,v in PARAMS[name].items()}
    if point=='minimum' and name=='CHAIKIN_OSCILLATOR': p['slow_length']=3
    if point=='maximum' and name in ('KAMA','CHAIKIN_OSCILLATOR'): p['fast_length']=4095
    return p

def first_valid(name,p):
    w=p.get('window',0)
    if name=='ADX': return 2*w-1
    if name=='CHAIKIN_OSCILLATOR': return p['slow_length']-1
    if name=='PARABOLIC_SAR': return 1
    if name in ('EMA','RMA_WILDER','PRICE_MA_DISTANCE'): return w-1
    return w

def fixture(kind='mixed', size=100):
    # Binary-exact base observations keep test origin separate from rounding noise.
    rows=[]
    for i in range(size):
        c=64+((i*17)%31-15)/4 + (i%7)/8
        h=c+1+(i%3)/4; l=c-1-(i%5)/8; v=10+(i*13)%41
        if kind=='flat': c=h=l=32.
        if kind=='zero': c=h=l=v=0.
        if kind=='ramp': c=float(i+1); h=c+1; l=c-1
        if kind=='ties': c=50.; h=51.+i%9; l=49.-i%9
        if kind=='impulse': c=64.+(100 if i==size//2 else 0); h=c+1;l=c-1
        if kind=='tiny': c*=1e-18;h*=1e-18;l*=1e-18;v*=1e-18
        if kind=='large': c*=2**40;h*=2**40;l*=2**40;v*=2**40
        if kind=='offset': c+=2**40;h+=2**40;l+=2**40
        row=dict(close=c,high=h,low=l,volume=float(v))
        if kind=='nonfinite' and i in (0,20,49,75):
            row={k:float('nan') if i%2==0 else float('inf') for k in row}
        if kind=='invalid_range' and i==size//2: row['low']=row['high']+1
        if kind=='negative_volume' and i==size//2: row['volume']=-1.
        if kind=='zero_close' and i in (0,25,50): row.update(close=0.,low=-1.,high=1.)
        rows.append(row)
    return rows

def segment(name,rows,p,trace=None):
    """Evaluate one finite input segment using high precision mathematical recurrences."""
    with localcontext() as ctx:
        ctx.prec=80
        data=[{k:D(v) for k,v in row.items()} for row in rows]
        w=p.get('window',0); out=[None]*len(rows); state={}
        gains=[]; losses=[]; trs=[]; ad=ZERO; ema=None; acc=ZERO; poisoned=False
        plus=minus=trsum=ZERO; dxs=[]; adx=None; path=ZERO
        def nearzero(x): return abs(x)<D(1e-14)
        for i,r in enumerate(data):
            c=r['close']; prev=data[i-1] if i else None; y=None
            if name in ('ACCUMULATION_DISTRIBUTION','CHAIKIN_OSCILLATOR'):
                span=r['high']-r['low']; add=ZERO if span==0 else ((2*c-r['high']-r['low'])/span)*r['volume']
                ad+=add
                if name=='ACCUMULATION_DISTRIBUTION': y=ad
                else:
                    if i==0: fast=slow=ad
                    else:
                        fast+=(Decimal(2)/(p['fast_length']+1))*(ad-fast)
                        slow+=(Decimal(2)/(p['slow_length']+1))*(ad-slow)
                    if i>=p['slow_length']-1:y=fast-slow
                    state.update(ad=ad,fast=fast,slow=slow)
            elif name=='CUMULATIVE_RETURN':
                origin=data[0]['close']; y=None if origin==0 else c/origin-1
                state['origin']=origin
            elif name=='OBV':
                if i==0:acc=r['volume']
                elif c>prev['close']:acc+=r['volume']
                elif c<prev['close']:acc-=r['volume']
                y=acc
            elif name=='PRICE_VOLUME_TREND':
                if i and prev['close']==0: poisoned=True
                if i and not poisoned:acc+=(c/prev['close']-1)*r['volume']
                y=None if poisoned else acc
            elif name in ('EMA','RMA_WILDER','MA_SLOPE','PRICE_MA_DISTANCE'):
                old=ema
                if i==w-1:ema=sum((z['close'] for z in data[:w]),ZERO)/w
                elif i>=w:
                    alpha=Decimal(1)/w if name=='RMA_WILDER' else Decimal(2)/(w+1)
                    ema+=alpha*(c-ema)
                if ema is not None:
                    y=c-ema if name=='PRICE_MA_DISTANCE' else (None if old is None else ema-old) if name=='MA_SLOPE' else ema
                state['ema']=ema
            elif name in ('ATR','NATR'):
                if i:
                    tr=max(r['high']-r['low'],abs(r['high']-prev['close']),abs(r['low']-prev['close'])); trs.append(tr)
                    if i==w:atr=sum(trs,ZERO)/w
                    elif i>w:atr=(atr*(w-1)+tr)/w
                    if i>=w:y=atr if name=='ATR' else (None if c==0 else 100*atr/c)
                    state['atr']=atr if i>=w else None
            elif name=='RSI':
                if i:
                    change=c-prev['close']; g=max(ZERO,change); loss=max(ZERO,-change)
                    gains.append(g);losses.append(loss)
                    if i==w:ag=sum(gains,ZERO)/w;al=sum(losses,ZERO)/w
                    elif i>w:ag=(ag*(w-1)+g)/w;al=(al*(w-1)+loss)/w
                    if i>=w:
                        y=ZERO if ag+al==0 else 100*ag/(ag+al)
                        state.update(gain=ag,loss=al)
            elif name=='KAMA':
                if i:path+=abs(c-prev['close'])
                if i>w:path-=abs(data[i-w]['close']-data[i-w-1]['close'])
                if i>=w:
                    er=Decimal(1) if path==0 else abs(c-data[i-w]['close'])/path
                    alpha=(er*(Decimal(2)/(p['fast_length']+1)-Decimal(2)/(p['slow_length']+1))+Decimal(2)/(p['slow_length']+1))**2
                    if i==w:kama=prev['close']
                    kama+=alpha*(c-kama);y=kama
                    state.update(path=path,efficiency=er,alpha=alpha,kama=kama)
            elif name in ('PLUS_DI','MINUS_DI','ADX'):
                if i:
                    up=r['high']-prev['high']; down=prev['low']-r['low']
                    pdm=up if up>0 and up>down else ZERO;mdm=down if down>0 and down>up else ZERO
                    tr=max(r['high']-r['low'],abs(r['high']-prev['close']),abs(r['low']-prev['close']))
                    if i<w:plus+=pdm;minus+=mdm;trsum+=tr
                    else:
                        plus=plus-plus/w+pdm;minus=minus-minus/w+mdm;trsum=trsum-trsum/w+tr
                        pi=ZERO if nearzero(trsum) else 100*plus/trsum;mi=ZERO if nearzero(trsum) else 100*minus/trsum
                        dx=None if nearzero(trsum) or nearzero(pi+mi) else 100*abs(pi-mi)/(pi+mi)
                        if name=='PLUS_DI':y=pi
                        elif name=='MINUS_DI':y=mi
                        else:
                            if i<2*w:dxs.append(ZERO if dx is None else dx)
                            if i==2*w-1:adx=sum(dxs,ZERO)/w
                            elif i>=2*w and dx is not None:adx=(adx*(w-1)+dx)/w
                            if i>=2*w-1:y=adx
                    state.update(plus=plus,minus=minus,tr=trsum,adx=adx)
            elif name=='PARABOLIC_SAR':
                if i:
                    if i==1:
                        up=r['high']-prev['high'];down=prev['low']-r['low'];long=not(down>0 and down>up)
                        ep=r['high'] if long else r['low'];sar=prev['low'] if long else prev['high'];af=D(p['start'])
                        ph=r['high'];pl=r['low']
                    else: ph=prev['high'];pl=prev['low']
                    reverse=(r['low']<=sar) if long else (r['high']>=sar)
                    if reverse:
                        long=not long
                        sar=min(ep,pl,r['low']) if long else max(ep,ph,r['high'])
                        af=D(p['start']);ep=r['high'] if long else r['low'];y=sar
                    else:
                        y=sar
                        if (long and r['high']>ep) or (not long and r['low']<ep):
                            ep=r['high'] if long else r['low'];af=min(D(p['maximum']),af+D(p['increment']))
                    sar+=af*(ep-sar)
                    sar=min(sar,pl,r['low']) if long else max(sar,ph,r['high'])
                    state.update(long=long,ep=ep,af=af,next_sar=sar,prior_high=r['high'],prior_low=r['low'])
            else:raise AssertionError(name)
            if y is not None and math.isfinite(float(y)):out[i]=float(y)
            if trace is not None:trace.append({'i':i,'value':out[i],'state':{k:str(v) for k,v in state.items()}})
        return out

def expected(name,rows,p,breaks=()):
    """Bad required inputs reset; undefined derived values do not erase origin/addends."""
    result=[None]*len(rows); start=0
    def flush(stop):
        if stop>start:result[start:stop]=segment(name,rows[start:stop],p)
    for i,r in enumerate(rows):
        good=all(k in r and math.isfinite(r[k]) for k in FIELDS[name])
        if 'high' in FIELDS[name] and good:good=r['high']>=r['low']
        if 'volume' in FIELDS[name] and good:good=r['volume']>=0
        if i in breaks:flush(i);start=i
        if not good:flush(i);start=i+1
    flush(len(rows));return result

def cases():
    for name in NAMES:
        for point in ('minimum','default','maximum'):
            p=parameters(name,point);n=max(96,first_valid(name,p)+80)
            yield dict(id=f'{name}-{point}-mixed',name=name,parameters=p,rows=fixture(size=n))
        for kind in ('flat','zero','ramp','ties','impulse','tiny','large','offset','nonfinite','invalid_range','negative_volume','zero_close'):
            yield dict(id=f'{name}-default-{kind}',name=name,parameters=parameters(name),rows=fixture(kind))
        yield dict(id=f'{name}-gaps',name=name,parameters=parameters(name),rows=fixture(size=160),breaks=[3,51,94])
    for f,s in [(4095,4096),(2047,2048),(127,128)]:
        yield dict(id=f'ADOSC-long-{f}-{s}',name='CHAIKIN_OSCILLATOR',parameters=dict(fast_length=f,slow_length=s),rows=fixture(size=12000))
    for p in [dict(start=.03,increment=.07,maximum=.4),dict(start=0.,increment=.1,maximum=.2)]:
        yield dict(id=f'SAR-unequal-{p["start"]}',name='PARABOLIC_SAR',parameters=p,rows=fixture(size=180))

def test_manual_seeds_and_cumulative_semantics():
    r=[dict(close=float(c),high=float(c+1),low=float(c-1),volume=10.) for c in [2,4,3,6]]
    assert expected('EMA',r,{'window':2})==[None,3.,3.,5.]
    assert expected('RMA_WILDER',r,{'window':2})==[None,3.,3.,4.5]
    assert expected('OBV',r,{})==[10.,20.,10.,20.]
    assert expected('CUMULATIVE_RETURN',r,{})==[0.,1.,.5,2.]
    assert expected('PRICE_VOLUME_TREND',r,{})==[0.,10.,7.5,17.5]
    assert expected('ATR',r,{'window':2})==[None,None,2.5,3.25]
    z=[dict(close=float(c),high=3.,low=-1.,volume=10.) for c in [0,1,2]]
    assert expected('CUMULATIVE_RETURN',z,{})==[None,None,None]
    assert expected('PRICE_VOLUME_TREND',z,{})==[0.,None,None]
