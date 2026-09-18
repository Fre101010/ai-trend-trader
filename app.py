from dataclasses import dataclass
import math
import numpy as np
import pandas as pd
import streamlit as st
import yaml

st.set_page_config(page_title="AI Trend Trader", page_icon="📈", layout="centered")

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 3rem; max-width: 820px;}
h1 {font-size: 2rem !important;}
.stButton > button {width:100%; min-height:56px; border-radius:14px; font-size:1.05rem; font-weight:700;}
div[data-testid="stMetric"] {border:1px solid rgba(128,128,128,.25); border-radius:16px; padding:12px;}
</style>
""", unsafe_allow_html=True)

with open("config.yaml","r",encoding="utf-8") as f:
    CFG=yaml.safe_load(f)

ASSETS = {
    "Crypto": {
        "BTC/EUR":"BTC/EUR",
        "ETH/EUR":"ETH/EUR",
        "SOL/EUR":"SOL/EUR",
    },
    "Forex": {
        "EUR/USD":"EURUSD=X",
        "GBP/USD":"GBPUSD=X",
        "USD/JPY":"JPY=X",
        "EUR/GBP":"EURGBP=X",
    },
    "Aandelen": {
        "Apple (AAPL)":"AAPL",
        "Microsoft (MSFT)":"MSFT",
        "NVIDIA (NVDA)":"NVDA",
        "Tesla (TSLA)":"TSLA",
    },
    "ETF's": {
        "S&P 500 ETF (SPY)":"SPY",
        "Nasdaq 100 ETF (QQQ)":"QQQ",
        "MSCI World ETF (URTH)":"URTH",
    },
    "Indices": {
        "S&P 500":"^GSPC",
        "Nasdaq 100":"^NDX",
        "DAX":"^GDAXI",
        "Euro Stoxx 50":"^STOXX50E",
    },
    "Grondstoffen": {
        "Goud":"GC=F",
        "Zilver":"SI=F",
        "Olie WTI":"CL=F",
        "Aardgas":"NG=F",
    },
}

def ema(s,n): return s.ewm(span=n,adjust=False).mean()

def rsi(s,n=14):
    d=s.diff()
    up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean()
    dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    rs=up/dn.replace(0,np.nan)
    return (100-(100/(1+rs))).fillna(50)

def atr(df,n=14):
    pc=df["close"].shift(1)
    tr=pd.concat([(df["high"]-df["low"]).abs(),
                  (df["high"]-pc).abs(),
                  (df["low"]-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n,adjust=False).mean()

def fetch_crypto(symbol,timeframe,limit=1000,exchange="kraken"):
    import ccxt
    ex=getattr(ccxt,exchange)({"enableRateLimit":True})
    ex.load_markets()
    rows=ex.fetch_ohlcv(symbol,timeframe=timeframe,limit=limit)
    df=pd.DataFrame(rows,columns=["timestamp","open","high","low","close","volume"])
    df["timestamp"]=pd.to_datetime(df["timestamp"],unit="ms",utc=True)
    return df.set_index("timestamp")

def fetch_yahoo(ticker,timeframe):
    import yfinance as yf
    # yfinance intraday history is limited; choose enough data for slow EMA where possible.
    mapping={
        "1h":("730d","60m"),
        "4h":("730d","60m"),  # resampled below
        "1d":("5y","1d"),
    }
    period,interval=mapping[timeframe]
    d=yf.download(ticker,period=period,interval=interval,auto_adjust=True,progress=False)
    if d.empty:
        raise RuntimeError("Geen marktdata ontvangen.")
    if isinstance(d.columns,pd.MultiIndex):
        d.columns=d.columns.get_level_values(0)
    d=d.rename(columns=str.lower)
    keep=["open","high","low","close","volume"]
    for c in keep:
        if c not in d.columns:
            d[c]=0.0
    d=d[keep].dropna(subset=["open","high","low","close"])
    if timeframe=="4h":
        agg={"open":"first","high":"max","low":"min","close":"last","volume":"sum"}
        d=d.resample("4h").agg(agg).dropna(subset=["open","high","low","close"])
    return d.tail(2000)

def enrich(df):
    c=CFG["strategy"]
    x=df.copy()
    x["ema_fast"]=ema(x["close"],c["fast_ema"])
    x["ema_mid"]=ema(x["close"],c["mid_ema"])
    x["ema_slow"]=ema(x["close"],c["slow_ema"])
    x["rsi"]=rsi(x["close"],c["rsi_period"])
    x["atr"]=atr(x,c["atr_period"])
    lb=c["breakout_lookback"]
    x["hh"]=x["high"].shift(1).rolling(lb).max()
    x["ll"]=x["low"].shift(1).rolling(lb).min()
    x["volavg"]=x["volume"].shift(1).rolling(lb).mean()
    return x

def trend_scores(r):
    long_score=0
    short_score=0
    if r["ema_fast"]>r["ema_mid"]>r["ema_slow"]: long_score+=2
    if r["ema_fast"]<r["ema_mid"]<r["ema_slow"]: short_score+=2
    if r["close"]>r["ema_fast"]: long_score+=1
    if r["close"]<r["ema_fast"]: short_score+=1
    if 52<=r["rsi"]<=75: long_score+=1
    if 25<=r["rsi"]<=48: short_score+=1
    if pd.notna(r["hh"]) and r["close"]>r["hh"]: long_score+=1
    if pd.notna(r["ll"]) and r["close"]<r["ll"]: short_score+=1
    return long_score,short_score

def size_for_risk(equity,entry,stop):
    risk_budget=equity*CFG["risk"]["risk_per_trade"]
    unit_risk=abs(entry-stop)
    if unit_risk<=0:return 0
    by_risk=risk_budget/unit_risk
    by_cap=(equity*CFG["risk"]["max_position_fraction"])/entry
    return max(0,min(by_risk,by_cap))

def run_backtest(raw,start_cash,allow_short=True):
    df=enrich(raw)
    cash=float(start_cash)
    peak=cash
    position=None
    trades=[]
    curve=[]
    fee=CFG["execution"]["fee_rate"]
    slip=CFG["execution"]["slippage"]
    c=CFG["strategy"]

    for i in range(len(df)):
        r=df.iloc[i]
        ts=df.index[i]
        if pd.isna(r["atr"]) or pd.isna(r["ema_slow"]):
            continue

        equity=cash
        if position:
            if position["side"]=="long":
                equity=cash+position["qty"]*r["close"]
            else:
                # short P/L marked to market against reserved entry notional
                equity=cash+position["margin"]+(position["entry"]-r["close"])*position["qty"]
        peak=max(peak,equity)
        curve.append((ts,equity))

        long_score,short_score=trend_scores(r)

        if position:
            side=position["side"]
            atrv=float(r["atr"])
            exit_px=None
            reason=None

            if side=="long":
                # ratchet trailing stop upward only
                candidate=float(r["close"])-c["trail_atr"]*atrv
                position["trail"]=max(position["trail"],candidate)

                # after +1R, lock at least break-even + estimated roundtrip costs
                if float(r["high"]) >= position["entry"] + c["profit_lock_r"]*position["initial_risk"]:
                    be=position["entry"]*(1+2*fee+2*slip)
                    position["trail"]=max(position["trail"],be)
                    position["locked"]=True

                reversal = short_score>=c["reversal_score_exit"] and short_score>long_score
                if float(r["low"])<=position["trail"]:
                    exit_px=position["trail"]*(1-slip); reason="Trailing/profit-lock"
                elif reversal and position["locked"]:
                    exit_px=float(r["close"])*(1-slip); reason="Bevestigde omkeer"

                if exit_px:
                    gross=position["qty"]*exit_px
                    cash+=gross-gross*fee
                    pnl=cash-position["equity_before"]
                    trades.append({
                        "Datum":str(ts),"Richting":"LONG","Entry":position["entry"],
                        "Exit":exit_px,"Resultaat €":pnl,"Reden":reason,
                        "Winst vergrendeld":position["locked"]
                    })
                    position=None
                    continue

            else:
                candidate=float(r["close"])+c["trail_atr"]*atrv
                position["trail"]=min(position["trail"],candidate)

                if float(r["low"]) <= position["entry"] - c["profit_lock_r"]*position["initial_risk"]:
                    be=position["entry"]*(1-2*fee-2*slip)
                    position["trail"]=min(position["trail"],be)
                    position["locked"]=True

                reversal = long_score>=c["reversal_score_exit"] and long_score>short_score
                if float(r["high"])>=position["trail"]:
                    exit_px=position["trail"]*(1+slip); reason="Trailing/profit-lock"
                elif reversal and position["locked"]:
                    exit_px=float(r["close"])*(1+slip); reason="Bevestigde omkeer"

                if exit_px:
                    pnl=(position["entry"]-exit_px)*position["qty"]
                    exit_fee=position["qty"]*exit_px*fee
                    cash+=position["margin"]+pnl-exit_fee
                    net=cash-position["equity_before"]
                    trades.append({
                        "Datum":str(ts),"Richting":"SHORT","Entry":position["entry"],
                        "Exit":exit_px,"Resultaat €":net,"Reden":reason,
                        "Winst vergrendeld":position["locked"]
                    })
                    position=None
                    continue
            continue

        if equity<=peak*(1-CFG["risk"]["max_drawdown"]):
            continue

        # Enter only one clear regime
        if long_score>=c["entry_score"] and long_score>short_score:
            entry=float(r["close"])*(1+slip)
            stop=entry-c["initial_stop_atr"]*float(r["atr"])
            qty=size_for_risk(cash,entry,stop)
            if qty<=0: continue
            notional=qty*entry
            entry_fee=notional*fee
            if notional+entry_fee>cash: continue
            before=cash
            cash-=notional+entry_fee
            position={"side":"long","entry":entry,"qty":qty,"trail":stop,
                      "initial_risk":entry-stop,"locked":False,"equity_before":before}

        elif allow_short and short_score>=c["entry_score"] and short_score>long_score:
            entry=float(r["close"])*(1-slip)
            stop=entry+c["initial_stop_atr"]*float(r["atr"])
            qty=size_for_risk(cash,entry,stop)
            if qty<=0: continue
            margin=qty*entry
            entry_fee=margin*fee
            if margin+entry_fee>cash: continue
            before=cash
            cash-=margin+entry_fee
            position={"side":"short","entry":entry,"qty":qty,"margin":margin,
                      "trail":stop,"initial_risk":stop-entry,"locked":False,
                      "equity_before":before}

    final=cash
    if position:
        last=float(df.iloc[-1]["close"])
        if position["side"]=="long":
            final+=position["qty"]*last*(1-fee)
        else:
            final+=position["margin"]+(position["entry"]-last)*position["qty"]-position["qty"]*last*fee

    tdf=pd.DataFrame(trades)
    cdf=pd.DataFrame(curve,columns=["timestamp","equity"]).set_index("timestamp")
    if not cdf.empty:
        dd=(cdf["equity"]/cdf["equity"].cummax()-1)*100
        maxdd=float(dd.min())
    else:maxdd=0.0
    pnls=tdf["Resultaat €"].tolist() if not tdf.empty else []
    wins=[p for p in pnls if p>0]; losses=[p for p in pnls if p<0]
    gp=sum(wins); gl=abs(sum(losses))
    pf=gp/gl if gl else (math.inf if gp else 0)
    return {
        "start":start_cash,"final":final,"return_pct":(final/start_cash-1)*100,
        "trades":len(tdf),"winrate":len(wins)/len(tdf)*100 if len(tdf) else 0,
        "profit_factor":pf,"maxdd":maxdd,
        "longs":int((tdf["Richting"]=="LONG").sum()) if not tdf.empty else 0,
        "shorts":int((tdf["Richting"]=="SHORT").sum()) if not tdf.empty else 0,
    },tdf,cdf,df

st.title("📈 AI Trend Trader")
st.caption("Multi-market oefenapp — long én short, winst laten lopen, uitstappen bij trendbreuk.")
st.success("🔒 Alleen backtest/paperconcept — echte orders staan uit.")

st.markdown("### 1. Markt kiezen")
market=st.selectbox("Markt",list(ASSETS.keys()))
label=st.selectbox("Instrument",list(ASSETS[market].keys()))
ticker=ASSETS[market][label]
timeframe_label=st.selectbox("Tijdsframe",["1 uur","4 uur","1 dag"],index=1)
timeframe={"1 uur":"1h","4 uur":"4h","1 dag":"1d"}[timeframe_label]
cash=st.number_input("Fictief startkapitaal (€)",min_value=500.0,value=5000.0,step=500.0)

short_default = market not in ["Aandelen","ETF's","Indices"]
allow_short=st.toggle("Short-posities testen",value=short_default,
    help="Shorten is niet op elk instrument/broker op dezelfde manier beschikbaar. Dit is alleen een simulatie.")

st.markdown("### 2. Strategie")
st.write("""
De bot probeert een duidelijke trend te volgen. Bij winst schuift de stop mee.
Na voldoende winst wordt minimaal break-even plus geschatte kosten beschermd.
De positie blijft open zolang de trend standhoudt en sluit bij een trailing stop
of bevestigde trendomkeer.
""")

if st.button("▶️ Start multi-market backtest",type="primary"):
    with st.spinner("Marktdata ophalen en trendstrategie testen..."):
        try:
            if market=="Crypto":
                raw=fetch_crypto(ticker,timeframe,1000,"kraken")
            else:
                raw=fetch_yahoo(ticker,timeframe)
            metrics,trades,curve,enriched=run_backtest(raw,cash,allow_short)
            st.session_state["res"]=(metrics,trades,curve,enriched,market,label)
            st.success("Backtest klaar.")
        except Exception as e:
            st.error("De test kon niet worden uitgevoerd.")
            st.code(str(e))

if "res" in st.session_state:
    m,trades,curve,enriched,market_used,label_used=st.session_state["res"]
    st.markdown("### 3. Resultaat")
    a,b=st.columns(2)
    a.metric("Eindwaarde",f"€{m['final']:,.2f}")
    b.metric("Rendement",f"{m['return_pct']:.2f}%")
    c,d=st.columns(2)
    c.metric("Winrate",f"{m['winrate']:.1f}%")
    d.metric("Max. drawdown",f"{m['maxdd']:.2f}%")
    e,f=st.columns(2)
    pf=m["profit_factor"]
    e.metric("Profit factor","∞" if math.isinf(pf) else f"{pf:.2f}")
    f.metric("Trades",m["trades"])
    st.caption(f"Longs: {m['longs']} · Shorts: {m['shorts']}")

    if not curve.empty:
        st.markdown("#### Evolutie fictief kapitaal")
        st.line_chart(curve["equity"])

    if not trades.empty:
        show=trades.copy()
        for col in ["Entry","Exit","Resultaat €"]:
            show[col]=show[col].round(2)
        with st.expander("Alle trades bekijken"):
            st.dataframe(show,use_container_width=True,hide_index=True)

st.divider()
st.markdown("### Belangrijk")
st.write("""
Een trendvolgende bot kan niet weten waar de exacte top of bodem ligt. Hij laat bewust
een deel van de beweging teruglopen voordat een omkeer bevestigd wordt. Daardoor kan hij
grote trends langer vasthouden, maar sommige trades zullen alsnog met verlies sluiten.
""")
st.warning("Live trading, leverage en echte broker/exchange-orders zijn in deze versie bewust niet ingebouwd.")
