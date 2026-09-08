"""Fresh independent exact-binary/rational oracle. Authored before product inspection.

Centered sums use the pairwise-difference identity: n*sum((x-mean)^2)
= sum_{i<j}(x_i-x_j)^2. No product imports or generated expected output.
Only final float64 conversion rounds. Irrational sqrt/log use 800 decimal digits.
"""
from fractions import Fraction as F
from decimal import Decimal, localcontext
import math

LEVEL = ('CORRELATION','R_SQUARED','ROLLING_HEDGE_RATIO','BETA_ADJUSTED_SPREAD',
         'COVARIANCE','LINEAR_REGRESSION_INTERCEPT','LINEAR_REGRESSION_SLOPE')
EXTENDED = ('ALPHA','BETA','CCI','ZSCORE','VOLUME_ZSCORE','RESIDUAL','ROLLING_REGRESSION',
            'PERCENT_RETURN','ROLLING_RETURN','ROC','LOG_RETURN')

def decimal(q):
    return Decimal(q.numerator)/Decimal(q.denominator)

def rounded(q):
    try:
        x=float(q)
        return x if math.isfinite(x) else math.nan
    except (OverflowError,ZeroDivisionError):
        return math.nan

def pair(a,b):
    return sum((a[i]-a[j])*(b[i]-b[j]) for i in range(len(a)) for j in range(i)) / len(a)

def moments(a,b):
    return pair(a,a),pair(b,b),pair(a,b)

def expectation(component, primary, peer=None, window=2, ddof=0):
    """Lists in -> complete named lists out. Invalid bars reset contiguous warmup."""
    ports=('slope','intercept','residual') if component=='ROLLING_REGRESSION' else ('value',)
    out={p:[math.nan]*len(primary) for p in ports}
    needs_peer=component in {'ALPHA','BETA','CORRELATION','R_SQUARED','ROLLING_HEDGE_RATIO',
                            'BETA_ADJUSTED_SPREAD','COVARIANCE','RESIDUAL','ROLLING_REGRESSION'}
    returns=component in {'ALPHA','BETA','PERCENT_RETURN','ROLLING_RETURN','ROC','LOG_RETURN'}
    width=window+int(returns)
    for end in range(width-1,len(primary)):
        ys=primary[end-width+1:end+1]
        xs=peer[end-width+1:end+1] if needs_peer else list(range(width))
        if not all(math.isfinite(v) for v in ys+xs):continue
        y=list(map(F,ys));x=list(map(F,xs))
        if component in {'PERCENT_RETURN','ROLLING_RETURN','ROC','LOG_RETURN'}:
            if y[0]==0 or (component=='LOG_RETURN' and (y[0]<=0 or y[-1]<=0)):continue
            q=y[-1]/y[0]
            with localcontext() as ctx:
                ctx.prec=800
                result=decimal(q).ln() if component=='LOG_RETURN' else q-1
            out['value'][end]=rounded(result);continue
        if component in {'ALPHA','BETA'}:
            if any(v==0 for v in x[:-1]+y[:-1]):continue
            x=[b/a-1 for a,b in zip(x,x[1:])];y=[b/a-1 for a,b in zip(y,y[1:])]
        n=len(y);mx=sum(x)/n;my=sum(y)/n
        vx,vy,cov=moments(x,y)
        if component=='COVARIANCE': result=cov/(n-ddof)
        elif component in {'CORRELATION','R_SQUARED'}:
            if vx==0 or vy==0:continue
            q=cov*cov/(vx*vy)
            if component=='R_SQUARED':result=q
            else:
                with localcontext() as ctx:
                    ctx.prec=800;result=decimal(q).sqrt() * (-1 if cov<0 else 1)
        elif component in {'CCI','ZSCORE','VOLUME_ZSCORE'}:
            if component=='CCI':
                dev=sum(abs(v-my) for v in y)/n
                result=(y[-1]-my)/(F(15,1000)*dev) if dev else F(0)
            else:
                if vy==0:continue
                with localcontext() as ctx:
                    ctx.prec=800;result=decimal(y[-1]-my)/decimal(vy/n).sqrt()
        else:
            if vx==0:continue
            slope=cov/vx;intercept=my-slope*mx;residual=y[-1]-intercept-slope*x[-1]
            if component=='ROLLING_REGRESSION':
                for port,q in zip(ports,(slope,intercept,residual)):out[port][end]=rounded(q)
                continue
            result={'ALPHA':intercept,'BETA':slope,'ROLLING_HEDGE_RATIO':slope,
                    'BETA_ADJUSTED_SPREAD':y[-1]-slope*x[-1],'RESIDUAL':residual,
                    'LINEAR_REGRESSION_INTERCEPT':intercept,'LINEAR_REGRESSION_SLOPE':slope}[component]
        out['value'][end]=rounded(result)
    return out

def level_cases():
    """Analytical signs, adjacent doubles, exact binary scaling, extremes and gaps."""
    cases={}
    offsets=[0,1,3,2,5,4,7,6,10,9,11,8,13,12,15,14,17,16]
    for exponent in (-500,-40,0,40,500):
        unit=math.ldexp(1.,exponent)
        x=[unit*(1+v/16) for v in offsets]
        cases[f'binary-linear-{exponent}']=( [2*v for v in x], x)
        cases[f'binary-negative-{exponent}']=([-2*v for v in x],x)
    for base in (1.,1e-100,1e100):
        x=[base+math.ulp(base)*v for v in offsets]
        cases[f'adjacent-positive-{base}']=([2*v for v in x],x)
        cases[f'adjacent-negative-{base}']=([-2*v for v in x],x)
    for value in (0.,1.,1e300,-1e300,math.ldexp(1.,-1000)):
        cases[f'constant-{value}']=([value]*18,[value]*18)
    x=[float(v+8) for v in offsets];y=[float(v*v%19-7) for v in offsets]
    cases['nonlinear']=(y,x)
    cases['constant-peer']=(y,[3.]*18)
    cases['constant-primary']=([7.]*18,x)
    for missing in (math.nan,math.inf,-math.inf):
        a=y.copy();b=x.copy();a[5]=missing;b[11]=missing
        cases[f'gap-{missing}']=(a,b)
    return cases

def return_cases():
    tiny=[1+math.ulp(1.)*v for v in [0,1,3,2,5,4,7,6,10,9,11,8,13,12,15,14,17,16]]
    return {'tiny':(tiny,[1+2*(v-1) for v in tiny]),
            'constant-third':([float(3**(17-i)) for i in range(18)], [float(3**(17-i)) for i in range(18)]),
            'positive-third-return':([float(4**i*3**(17-i)) for i in range(18)],[float(4**i*3**(17-i)) for i in range(18)]),
            'extreme-endpoints':([1e-300,1e300,1e-250,1e250,1e-200,1e200]*3,[2.,3.,5.,7.,11.,13.]*3)}

def test_pair_identity_and_sign():
    assert pair(list(map(F,[1,2,3])),list(map(F,[1,2,3])))==2
    for sign in (-1,1):
        a=[1.,math.nextafter(1.,math.inf)];b=[sign*2*v for v in a]
        assert expectation('CORRELATION',b,a)['value'][1]==sign
        assert expectation('ROLLING_HEDGE_RATIO',b,a)['value'][1]==2*sign
        assert expectation('BETA_ADJUSTED_SPREAD',b,a)['value'][1]==0
    assert expectation('COVARIANCE',[2.,4.],[1.,2.],ddof=0)['value'][1]==.5
    assert expectation('COVARIANCE',[2.,4.],[1.,2.],ddof=1)['value'][1]==1

def test_oldest_origin_and_constant_thirds():
    assert expectation('LINEAR_REGRESSION_INTERCEPT',[7.,10.,13.],window=3)['value'][2]==7
    for name,(y,x) in return_cases().items():
        if 'third' in name:
            assert all(math.isnan(v) for v in expectation('BETA',y,x)['value'])
    assert expectation('LINEAR_REGRESSION_SLOPE',[1e300]*3,window=3)['value'][2]==0
