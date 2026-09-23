from __future__ import annotations
import numpy as np, pandas as pd, yfinance as yf, yaml

with open('config.yaml','r',encoding='utf-8') as f:
    CFG=yaml.safe_load(f)

def ema(s,n): return s.ewm(span=n,adjust=False).mean()

def rsi(s,n=14):
    d=s.diff()
    u=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean()
    v=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    rs=u/v.replace(0,np.nan)
    return (100-100/(1+rs)).fillna(50)

def atr(d,n=14):
    pc=d.close.shift()
    tr=pd.concat([(d.high-d.low).abs(),(d.high-pc).abs(),(d.low-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n,adjust=False).mean()

def adx(d,n=14):
    up=d.high.diff(); dn=-d.low.diff()
    pdm=up.where((up>dn)&(up>0),0.0); mdm=dn.where((dn>up)&(dn>0),0.0)
    pc=d.close.shift()
    tr=pd.concat([(d.high-d.low).abs(),(d.high-pc).abs(),(d.low-pc).abs()],axis=1).max(axis=1)
    a=tr.ewm(alpha=1/n,adjust=False).mean().replace(0,np.nan)
    p=100*pdm.ewm(alpha=1/n,adjust=False).mean()/a
    m=100*mdm.ewm(alpha=1/n,adjust=False).mean()/a
    dx=100*(p-m).abs()/(p+m).replace(0,np.nan)
    return dx.ewm(alpha=1/n,adjust=False).mean().fillna(0),p.fillna(0),m.fillna(0)

def fetch(ticker,tf):
    # Yahoo/yfinance can intermittently return an empty intraday response.
    # Try progressively smaller windows before declaring the feed unavailable.
    candidates={
        '1d':[('5y','1d'),('2y','1d'),('1y','1d')],
        '4h':[('730d','60m'),('180d','60m'),('60d','60m')],
        '1h':[('730d','60m'),('180d','60m'),('60d','60m')],
        '15m':[('60d','15m'),('30d','15m'),('10d','15m'),('5d','15m')],
    }[tf]

    last_error=None
    d=None

    for period,interval in candidates:
        try:
            x=yf.download(
                ticker,
                period=period,
                interval=interval,
                auto_adjust=True,
                progress=False,
                threads=False,
            )
            if x is None or x.empty:
                continue

            if isinstance(x.columns,pd.MultiIndex):
                x.columns=x.columns.get_level_values(0)

            x=x.rename(columns=str.lower)
            for c in ['open','high','low','close','volume']:
                if c not in x.columns:
                    x[c]=0.0

            x=x[['open','high','low','close','volume']].dropna(
                subset=['open','high','low','close']
            )

            if x.empty:
                continue

            d=x
            break
        except Exception as e:
            last_error=e
            continue

    if d is None or d.empty:
        detail=f" ({type(last_error).__name__})" if last_error else ""
        raise RuntimeError(f'Geen actuele koersdata voor {ticker}{detail}')

    if tf=='4h':
        d=d.resample('4h').agg({
            'open':'first',
            'high':'max',
            'low':'min',
            'close':'last',
            'volume':'sum'
        }).dropna()

    if d.empty:
        raise RuntimeError(f'Geen bruikbare {tf}-data voor {ticker}')

    return d

def enrich(d,p):
    x=d.copy()
    x['ef']=ema(x.close,p['fast_ema']); x['em']=ema(x.close,p['mid_ema']); x['es']=ema(x.close,p['slow_ema'])
    x['rsi']=rsi(x.close); x['atr']=atr(x); x['adx'],x['pdi'],x['mdi']=adx(x)
    x['hh']=x.high.shift().rolling(20).max(); x['ll']=x.low.shift().rolling(20).min()
    x['regmid']=ema(x.close,max(p['mid_ema']*2,p['mid_ema']+20))
    x['regslow']=ema(x.close,max(p['slow_ema'],p['mid_ema']*3))
    x['bullreg']=(x.regmid>x.regslow)&(x.close>x.regmid)
    x['bearreg']=(x.regmid<x.regslow)&(x.close<x.regmid)
    return x

def scores(r):
    L=S=0
    if r.ef>r.em>r.es:L+=2
    if r.ef<r.em<r.es:S+=2
    if r.close>r.ef:L+=1
    if r.close<r.ef:S+=1
    if r.pdi>r.mdi:L+=1
    if r.mdi>r.pdi:S+=1
    if 52<=r.rsi<=74:L+=1
    if 26<=r.rsi<=48:S+=1
    if pd.notna(r.hh) and r.close>r.hh:L+=1
    if pd.notna(r.ll) and r.close<r.ll:S+=1
    if r.bullreg:L+=2
    if r.bearreg:S+=2
    L+=1; S=max(0,S-1)
    return L,S

def market_snapshot(asset, mode="swing"):
    meta=CFG['portfolio']['assets'][asset]
    p=CFG['profiles'][meta['profile']]
    tfs=['1d','4h','1h'] if mode=='swing' else ['4h','1h','15m']
    out={}
    for tf in tfs:
        e=enrich(fetch(meta['ticker'],tf),p)
        # Intraday Yahoo data can contain a still-forming candle.
        # For signal generation we intentionally use the latest CLOSED candle
        # so a valid setup is stable and cannot disappear mid-candle.
        signal_row = -2 if tf in ['15m','1h','4h'] and len(e) >= 2 else -1
        r=e.iloc[signal_row]
        L,S=scores(r)
        trend='BULLISH' if L>S and bool(r.bullreg) else ('BEARISH' if S>L and bool(r.bearreg) else 'NEUTRAAL')
        out[tf]={
            'trend':trend,'L':int(L),'S':int(S),'adx':float(r.adx),'rsi':float(r.rsi),
            'price':float(r.close),'atr':float(r.atr),'ema20':float(r.ef),
            'ema50':float(r.em),'ema200':float(r.es),'time':str(e.index[signal_row])
        }
    return out


def desired_action(asset,s,mode="swing"):
    meta=CFG['portfolio']['assets'][asset]
    p=CFG['profiles'][meta['profile']]
    profile=meta['profile']

    if mode=='active':
        h4=s['4h']; h1=s['1h']; m15=s['15m']

        long_regime=(
            h4['trend']=='BULLISH'
            and h4['price']>h4['ema50']
            and h4['adx']>=max(16,p.get('min_adx',18)-2)
        )
        long_confirm=(
            h1['trend']=='BULLISH'
            and h1['price']>h1['ema20']
            and h1['L']>=h1['S']
        )
        long_timing=(
            m15['L']>=m15['S']
            and 45<=m15['rsi']<=72
            and m15['price']>m15['ema20']
        )

        short_regime=(
            h4['trend']=='BEARISH'
            and h4['price']<h4['ema50']
            and h4['adx']>=max(16,p.get('min_adx',18)-2)
        )
        short_confirm=(
            h1['trend']=='BEARISH'
            and h1['price']<h1['ema20']
            and h1['S']>=h1['L']
        )
        short_timing=(
            m15['S']>=m15['L']
            and 28<=m15['rsi']<=55
            and m15['price']<m15['ema20']
        )

        if long_regime and long_confirm and long_timing:
            return 'LONG'
        if short_regime and short_confirm and short_timing:
            return 'SHORT'
        return 'CASH'

    if profile=='crypto':
        d=s['1d']; h4=s['4h']; h1=s['1h']
        bull=(
            d['trend']=='BULLISH'
            and d['price']>d['ema200']
            and d['ema50']>d['ema200']
            and d['adx']>=p.get('min_adx',18)
        )
        conf=(
            h4['trend']=='BULLISH'
            and h4['adx']>=p.get('min_adx_4h',16)
            and h4['price']>h4['ema50']
        )
        timing=(
            h1['L']>=h1['S']
            and p.get('rsi_min_1h',44)<=h1['rsi']<=p.get('rsi_max_1h',72)
            and h1['price']>h1['ema20']
        )
        return 'LONG' if bull and conf and timing else 'CASH'

    if s['1d']['trend']=='BULLISH' and s['4h']['trend']=='BULLISH':
        return 'LONG' if s['1h']['trend'] in ['BULLISH','NEUTRAAL'] else 'WAIT'
    return 'CASH'

def size_for_risk(capital,price,stop,risk_multiplier=1.0,risk_pct=None):
    rp = CFG['risk']['risk_per_trade'] if risk_pct is None else float(risk_pct)/100.0
    rb=capital*rp*float(risk_multiplier)
    u=abs(price-stop)
    return 0 if u<=0 else max(0,min(rb/u,(capital*CFG['risk']['max_position_fraction'])/price))


def active_diagnostics(asset, s):
    """Return transparent Active long/short filter diagnostics."""
    meta=CFG["portfolio"]["assets"][asset]
    p=CFG["profiles"][meta["profile"]]

    h4=s["4h"]
    h1=s["1h"]
    m15=s["15m"]

    min_adx=max(16,p.get("min_adx",18)-2)

    checks_long = {
        "4H trend bullish": h4["trend"]=="BULLISH",
        "4H boven EMA50": h4["price"]>h4["ema50"],
        f"4H ADX ≥ {min_adx:.0f}": h4["adx"]>=min_adx,
        "1H trend bullish": h1["trend"]=="BULLISH",
        "1H boven EMA20": h1["price"]>h1["ema20"],
        "1H longscore ≥ shortscore": h1["L"]>=h1["S"],
        "15m longscore ≥ shortscore": m15["L"]>=m15["S"],
        "15m RSI 45–72": 45<=m15["rsi"]<=72,
        "15m boven EMA20": m15["price"]>m15["ema20"],
    }

    checks_short = {
        "4H trend bearish": h4["trend"]=="BEARISH",
        "4H onder EMA50": h4["price"]<h4["ema50"],
        f"4H ADX ≥ {min_adx:.0f}": h4["adx"]>=min_adx,
        "1H trend bearish": h1["trend"]=="BEARISH",
        "1H onder EMA20": h1["price"]<h1["ema20"],
        "1H shortscore ≥ longscore": h1["S"]>=h1["L"],
        "15m shortscore ≥ longscore": m15["S"]>=m15["L"],
        "15m RSI 28–55": 28<=m15["rsi"]<=55,
        "15m onder EMA20": m15["price"]<m15["ema20"],
    }

    long_ok=all(checks_long.values())
    short_ok=all(checks_short.values())

    if long_ok:
        action="LONG"
        reasons=["Alle LONG-filters OK"]
    elif short_ok:
        action="SHORT"
        reasons=["Alle SHORT-filters OK"]
    else:
        action="CASH"
        # Show the most useful failed LONG checks first when trend is bullish,
        # otherwise failed SHORT checks.
        if h4["trend"]=="BULLISH" or h1["trend"]=="BULLISH":
            reasons=[name for name,ok in checks_long.items() if not ok]
        elif h4["trend"]=="BEARISH" or h1["trend"]=="BEARISH":
            reasons=[name for name,ok in checks_short.items() if not ok]
        else:
            reasons=["Geen overtuigend 4H/1H regime"]

    return {
        "action": action,
        "reasons": reasons,
        "long_checks": checks_long,
        "short_checks": checks_short,
        "adx_4h": float(h4["adx"]),
        "rsi_15m": float(m15["rsi"]),
        "last_15m_candle": m15.get("time"),
        "last_1h_candle": h1.get("time"),
        "last_4h_candle": h4.get("time"),
    }
