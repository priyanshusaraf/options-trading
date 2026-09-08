"""Independent correction oracle, authored from accepted prose before product inspection.

All finite binary64 observations become exact Fractions. Only the final irrational
sqrt/log and binary64 presentation round. Decimal precision/context is explicit;
no finite-precision return calculation decides whether variance is zero.
"""
from decimal import Context, Decimal, localcontext
from fractions import Fraction as Q
import math

NAMES = tuple('ALPHA BETA BETA_ADJUSTED_SPREAD CCI CHAIKIN_MONEY_FLOW CORRELATION COVARIANCE CROSS_ABOVE CROSS_BELOW FALLING GAP GAP_DOWN GAP_UP HL2 HLC3 INSIDE_BAR LINEAR_REGRESSION_INTERCEPT LINEAR_REGRESSION_SLOPE LOG_RETURN MAD MFI MIDPOINT MOMENTUM OHLC4 OUTSIDE_BAR PERCENTILE PERCENTILE_RANK PERCENT_RETURN POINT_CHANGE RATIO RELATIVE_VOLUME RESIDUAL RISING ROC ROLLING_HEDGE_RATIO ROLLING_HIGH ROLLING_LOW ROLLING_MAX ROLLING_MEAN ROLLING_MEDIAN ROLLING_MIN ROLLING_RANK ROLLING_REGRESSION ROLLING_RETURN ROLLING_STDDEV ROLLING_VARIANCE ROLLING_VOLUME_PERCENTILE R_SQUARED SMA TREND_PERSISTENCE TRUE_RANGE TYPICAL_PRICE VOLUME_ZSCORE VWMA WEIGHTED_CLOSE WILLIAMS_R WMA ZSCORE'.split())
EXTENSIONS = ('ALPHA', 'BETA', 'CCI', 'ZSCORE', 'VOLUME_ZSCORE', 'RESIDUAL', 'ROLLING_REGRESSION', 'PERCENTILE', 'PERCENT_RETURN', 'ROLLING_RETURN', 'ROC', 'LOG_RETURN', 'LINEAR_REGRESSION_SLOPE', 'LINEAR_REGRESSION_INTERCEPT', 'CORRELATION', 'MFI')
CTX = Context(prec=160, Emin=-999999, Emax=999999)

def mean(v): return sum(v, Q(0))/len(v)
def rational(v): return Q(float(v))
def decimal(v): return Decimal(v.numerator)/Decimal(v.denominator)
def root(v):
    with localcontext(CTX): return float(decimal(v).sqrt())
def logarithm(v):
    with localcontext(CTX): return float(decimal(v).ln())
def finite(v):
    try: return math.isfinite(float(v))
    except (OverflowError, TypeError, ValueError): return False

def expected(name, data, window=14, q=50, breaks=()):
    """Every position and every named mask; breaks mark first row after a gap."""
    n=len(data['close']); ports=('slope','intercept','residual') if name=='ROLLING_REGRESSION' else ('value',)
    out={p:[None]*n for p in ports}
    fields={'CCI':('high','low','close'), 'VOLUME_ZSCORE':('volume',), 'MFI':('high','low','close','volume')}.get(name,('close','peer') if name in ('ALPHA','BETA','RESIDUAL','ROLLING_REGRESSION','CORRELATION') else ('close',))
    lag=name in ('ALPHA','BETA','PERCENT_RETURN','ROLLING_RETURN','ROC','LOG_RETURN','MFI')
    size=window+1 if lag else window
    begin=0
    for t in range(n):
        if t in breaks: begin=t
        if any(not finite(data[f][t]) for f in fields): begin=t+1; continue
        if t-begin+1<size: continue
        v={f:[rational(x) for x in data[f][t-size+1:t+1]] for f in fields}
        result={}
        if name in ('PERCENT_RETURN','ROLLING_RETURN','ROC','LOG_RETURN'):
            a,b=v['close'][0],v['close'][-1]
            if a==0 or (name=='LOG_RETURN' and (a<=0 or b<=0)):continue
            result['value']=logarithm(b/a) if name=='LOG_RETURN' else b/a-1
        elif name in ('ALPHA','BETA','RESIDUAL','ROLLING_REGRESSION','CORRELATION','LINEAR_REGRESSION_SLOPE','LINEAR_REGRESSION_INTERCEPT'):
            y=v['close']; x=v.get('peer',[Q(i) for i in range(window)])
            if name in ('ALPHA','BETA'):
                if any(z==0 for z in x[:-1]+y[:-1]):continue
                x=[b/a-1 for a,b in zip(x,x[1:])];y=[b/a-1 for a,b in zip(y,y[1:])]
            xm,ym=mean(x),mean(y)
            xx=sum((z-xm)**2 for z in x);xy=sum((a-xm)*(b-ym) for a,b in zip(x,y))
            if xx==0:continue
            slope=xy/xx;intercept=ym-slope*xm;residual=y[-1]-intercept-slope*x[-1]
            if name=='ROLLING_REGRESSION':result=dict(slope=slope,intercept=intercept,residual=residual)
            elif name=='CORRELATION':
                yy=sum((z-ym)**2 for z in y)
                if yy==0:continue
                result['value']=(-1 if xy<0 else 1)*root(xy*xy/(xx*yy))
            else:result['value']={'ALPHA':intercept,'BETA':slope,'RESIDUAL':residual,'LINEAR_REGRESSION_SLOPE':slope,'LINEAR_REGRESSION_INTERCEPT':intercept}[name]
        elif name in ('CCI','ZSCORE','VOLUME_ZSCORE'):
            x=[(h+l+c)/3 for h,l,c in zip(v['high'],v['low'],v['close'])] if name=='CCI' else v['volume' if name=='VOLUME_ZSCORE' else 'close']
            center=mean(x);diff=x[-1]-center
            if name=='CCI':
                mad=mean([abs(z-center) for z in x]);result['value']=diff/(Q(3,200)*mad) if mad else Q(0)
            else:
                variance=mean([(z-center)**2 for z in x])
                if variance==0:continue
                result['value']=(-1 if diff<0 else 1)*root(diff*diff/variance)
        elif name=='PERCENTILE':
            x=sorted(v['close']);h=(window-1)*rational(q)/100;i=h.numerator//h.denominator;f=h-i
            result['value']=x[i] if i==window-1 else x[i]+f*(x[i+1]-x[i])
        elif name=='MFI':
            tp=[(h+l+c)/3 for h,l,c in zip(v['high'],v['low'],v['close'])]
            pos=sum((b*vol for a,b,vol in zip(tp,tp[1:],v['volume'][1:]) if b>a),Q(0))
            neg=sum((b*vol for a,b,vol in zip(tp,tp[1:],v['volume'][1:]) if b<a),Q(0))
            result['value']=Q(0) if pos+neg<1 else 100*pos/(pos+neg)
        else:raise ValueError(name)
        for port,value in result.items():
            if finite(value):out[port][t]=float(value)
    return out

def fixtures():
    cases={}
    # Each integer 3**k, k<=32, is below 2**53. Consecutive ratios are
    # EXACTLY 1/3 in Q: all peer simple returns equal -2/3, variance zero.
    peer=[float(3**k) for k in range(32,-1,-1)]
    y=[float(2**k) for k in range(32,-1,-1)]
    cases['constant_thirds']={'close':y,'peer':peer}
    for exponent in (0,40,500,-500):
        x=[math.ldexp(1+(i%7)*2**-50,exponent) for i in range(39)]
        cases[f'exact_double_{exponent}']={'close':[2*z for z in x],'peer':x}
    for scale in (1.0,1e12,1e-200):
        unit=math.ulp(scale)
        x=[scale+unit*((i*7)%19-9) for i in range(43)]
        peer=[scale+unit*((i*11)%23-11) for i in range(43)]
        cases[f'near_flat_{scale}']=dict(close=x,peer=peer,high=x.copy(),low=x.copy(),volume=x.copy())
    for scale in (1e308,1e-300):
        cases[f'constant_{scale}']={f:[scale]*35 for f in ('close','peer','high','low','volume')}
    cases['extreme_log']={'close':[1e-300,1e300,1e-200,1e200,1.0,2.0,1.0]*5}
    cases['quantile_ties']={'close':[1.,9.,2.,2.,7.,4.,3.,8.,6.,5.]*4}
    cases['ols_long']={'close':[float(2*i+3) for i in range(4100)]}
    cases['two_point_correlation']={'close':[1.,4.,2.,7.,3.], 'peer':[4.,1.,7.,3.,9.]}
    cases['mfi_small']={'close':[1.,2.,3.,2.,1.,2.], 'high':[1.,2.,3.,2.,1.,2.], 'low':[1.,2.,3.,2.,1.,2.], 'volume':[.01]*6}
    return cases

def test_exact_thirds_have_zero_variance():
    p=list(map(rational,fixtures()['constant_thirds']['peer']))
    returns=[b/a-1 for a,b in zip(p,p[1:])]
    assert set(returns)=={Q(-2,3)}
    for name in ('ALPHA','BETA'):
        assert expected(name,fixtures()['constant_thirds'],2)=={'value':[None]*33}

def test_binary_scaled_linear_identities():
    for key,data in fixtures().items():
        if not key.startswith('exact_double'):continue
        out=expected('ROLLING_REGRESSION',data,7)
        assert out=={'slope':[None]*6+[2.]*33,'intercept':[None]*6+[0.]*33,'residual':[None]*6+[0.]*33}

def test_closed_form_long_ols():
    d=fixtures()['ols_long'];n=len(d['close'])
    assert expected('LINEAR_REGRESSION_SLOPE',d,4096)['value']==[None]*4095+[2.]*(n-4095)
    assert expected('LINEAR_REGRESSION_INTERCEPT',d,4096)['value']==[None]*4095+[float(3+2*i) for i in range(n-4095)]

def test_own_constant_and_quantile_identities():
    d=fixtures()['constant_1e+308']
    assert expected('CCI',d,2)['value']==[None]+[0.]*34
    assert expected('ZSCORE',d,2)['value']==[None]*35
    assert expected('PERCENTILE',{'close':[1,2,9,10]},4,50)['value']==[None]*3+[5.5]
