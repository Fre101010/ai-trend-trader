import math
from copy import deepcopy
import numpy as np
import pandas as pd
import streamlit as st
import yaml

st.set_page_config(page_title="AI Trend Trader v0.5", page_icon="📈", layout="centered")
st.markdown("""<style>
.block-container{padding-top:1rem;padding-bottom:4rem;max-width:900px}
.stButton>button{width:100%;min-height:56px;border-radius:14px;font-weight:700}
div[data-testid="stMetric"]{border:1px solid rgba(128,128,128,.25);border-radius:16px;padding:12px}
</style>""",unsafe_allow_html=True)

with open("config.yaml","r",encoding="utf-8") as f: CFG=yaml.safe_load(f)

ASSETS={
"Crypto":{"BTC/EUR":"BTC/EUR","ETH/EUR":"ETH/EUR","SOL/EUR":"SOL/EUR"},
"Forex":{"EUR/USD":"EURUSD=X","GBP/USD":"GBPUSD=X","USD/JPY":"JPY=X","EUR/GBP":"EURGBP=X"},
"Aandelen":{"Apple":"AAPL","Microsoft":"MSFT","NVIDIA":"NVDA","Tesla":"TSLA","Amazon":"AMZN","Alphabet":"GOOGL"},
"ETF's":{"S&P 500 ETF":"SPY","Nasdaq 100 ETF":"QQQ","MSCI World ETF":"URTH"},
"Indices":{"S&P 500":"^GSPC","Nasdaq 100":"^NDX","DAX":"^GDAXI","Euro Stoxx 50":"^STOXX50E"},
"Grondstoffen":{"Goud":"GC=F","Zilver":"SI=F","Olie WTI":"CL=F","Aardgas":"NG=F"}}

def pname(m,l):
    if m=="Crypto": return "crypto"
    if m=="Forex": return "forex"
    if m in ["Aandelen","ETF's","Indices"]: return "stocks"
    if m=="Grondstoffen" and l=="Goud": return "gold"
    return "commodities"

def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def rsi(s,n=14):
    d=s.diff();u=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean();v=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return (100-100/(1+u/v.replace(0,np.nan))).fillna(50)
def atr(d,n=14):
    pc=d.close.shift();tr=pd.concat([(d.high-d.low).abs(),(d.high-pc).abs(),(d.low-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n,adjust=False).mean()
def adx(d,n=14):
    up=d.high.diff();dn=-d.low.diff()
    pdm=up.where((up>dn)&(up>0),0.0);mdm=dn.where((dn>up)&(dn>0),0.0)
    pc=d.close.shift();tr=pd.concat([(d.high-d.low).abs(),(d.high-pc).abs(),(d.low-pc).abs()],axis=1).max(axis=1)
    a=tr.ewm(alpha=1/n,adjust=False).mean().replace(0,np.nan)
    p=100*pdm.ewm(alpha=1/n,adjust=False).mean()/a;m=100*mdm.ewm(alpha=1/n,adjust=False).mean()/a
    dx=100*(p-m).abs()/(p+m).replace(0,np.nan)
    return dx.ewm(alpha=1/n,adjust=False).mean().fillna(0),p.fillna(0),m.fillna(0)

@st.cache_data(ttl=3600,show_spinner=False)
def get_data(market,ticker,tf):
    if market=="Crypto":
        import ccxt
        ex=ccxt.kraken({"enableRateLimit":True}); ex.load_markets()
        rows=ex.fetch_ohlcv(ticker,timeframe=tf,limit=1000)
        d=pd.DataFrame(rows,columns=["timestamp","open","high","low","close","volume"])
        d["timestamp"]=pd.to_datetime(d.timestamp,unit="ms",utc=True);return d.set_index("timestamp")
    import yfinance as yf
    period,interval={"1h":("730d","60m"),"4h":("730d","60m"),"1d":("8y","1d")}[tf]
    d=yf.download(ticker,period=period,interval=interval,auto_adjust=True,progress=False)
    if d.empty: raise RuntimeError("Geen marktdata ontvangen")
    if isinstance(d.columns,pd.MultiIndex): d.columns=d.columns.get_level_values(0)
    d=d.rename(columns=str.lower)
    for c in ["open","high","low","close","volume"]:
        if c not in d.columns:d[c]=0.0
    d=d[["open","high","low","close","volume"]].dropna(subset=["open","high","low","close"])
    if tf=="4h":
        d=d.resample("4h").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    return d.tail(3000)

def enrich(d,p):
    x=d.copy()
    x["ef"]=ema(x.close,p["fast_ema"]);x["em"]=ema(x.close,p["mid_ema"]);x["es"]=ema(x.close,p["slow_ema"])
    x["rsi"]=rsi(x.close);x["atr"]=atr(x);x["adx"],x["pdi"],x["mdi"]=adx(x)
    x["hh"]=x.high.shift().rolling(20).max();x["ll"]=x.low.shift().rolling(20).min()
    # slower regime filter
    x["regmid"]=ema(x.close,max(p["mid_ema"]*2,p["mid_ema"]+20))
    x["regslow"]=ema(x.close,max(p["slow_ema"],p["mid_ema"]*3))
    x["bullreg"]=(x.regmid>x.regslow)&(x.close>x.regmid)
    x["bearreg"]=(x.regmid<x.regslow)&(x.close<x.regmid)
    return x

def scores(r,market):
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
    if market in ["Aandelen","ETF's","Indices"]: L+=1;S=max(0,S-1)
    return L,S

def size(equity,entry,stop):
    rb=equity*CFG["risk"]["risk_per_trade"];u=abs(entry-stop)
    return 0 if u<=0 else max(0,min(rb/u,(equity*CFG["risk"]["max_position_fraction"])/entry))

def backtest(raw,cash0,market,label,tf,allow_short):
    p=deepcopy(CFG["profiles"][pname(market,label)]);d=enrich(raw,p)
    fee=CFG["execution"]["fee_rate_crypto"] if market=="Crypto" else CFG["execution"]["fee_rate_other"]
    slip=CFG["execution"]["slippage_crypto"] if market=="Crypto" else CFG["execution"]["slippage_other"]
    cash=float(cash0);peak=cash;pos=None;tr=[];curve=[]
    for i in range(max(p["slow_ema"],205),len(d)):
        r=d.iloc[i];ts=d.index[i]
        eq=cash if pos is None else (cash+pos["q"]*r.close if pos["side"]=="L" else cash+pos["margin"]+(pos["entry"]-r.close)*pos["q"])
        peak=max(peak,eq);curve.append((ts,eq));L,S=scores(r,market)
        if pos:
            px=float(r.close);av=float(r.atr);xp=None;reason=None
            mult=p["trail_atr"]*(1.15 if r.adx>=p["min_adx"]+10 else 1.0)
            if pos["side"]=="L":
                pos["trail"]=max(pos["trail"],px-mult*av)
                if r.high>=pos["entry"]+p["profit_lock_r"]*pos["risk"]:
                    pos["trail"]=max(pos["trail"],pos["entry"]*(1+2*fee+2*slip));pos["locked"]=True
                if r.low<=pos["trail"]:xp=pos["trail"]*(1-slip);reason="Trailing/profit-lock"
                elif pos["locked"] and r.ef<r.em and S>L:xp=px*(1-slip);reason="Trendbreuk"
                if xp:
                    gross=pos["q"]*xp;cash+=gross-gross*fee;pnl=cash-pos["before"]
                    tr.append([str(ts),"LONG",pos["entry"],xp,pnl,reason]);pos=None;continue
            else:
                pos["trail"]=min(pos["trail"],px+mult*av)
                if r.low<=pos["entry"]-p["profit_lock_r"]*pos["risk"]:
                    pos["trail"]=min(pos["trail"],pos["entry"]*(1-2*fee-2*slip));pos["locked"]=True
                if r.high>=pos["trail"]:xp=pos["trail"]*(1+slip);reason="Trailing/profit-lock"
                elif pos["locked"] and r.ef>r.em and L>S:xp=px*(1+slip);reason="Trendbreuk"
                if xp:
                    pnl=(pos["entry"]-xp)*pos["q"];cash+=pos["margin"]+pnl-pos["q"]*xp*fee;net=cash-pos["before"]
                    tr.append([str(ts),"SHORT",pos["entry"],xp,net,reason]);pos=None;continue
            continue
        if eq<=peak*(1-CFG["risk"]["max_drawdown"]) or r.adx<p["min_adx"]:continue
        long_ok=L>=p["entry_score"] and L>S and bool(r.bullreg)
        short_req=p["entry_score"]+(2 if market in ["Aandelen","ETF's","Indices"] else 0)
        short_ok=allow_short and S>=short_req and S>L and bool(r.bearreg)
        if long_ok:
            en=float(r.close)*(1+slip);stp=en-p["initial_stop_atr"]*float(r.atr);q=size(cash,en,stp);notional=q*en;efee=notional*fee
            if q>0 and notional+efee<=cash:
                before=cash;cash-=notional+efee;pos={"side":"L","entry":en,"q":q,"trail":stp,"risk":en-stp,"locked":False,"before":before}
        elif short_ok:
            en=float(r.close)*(1-slip);stp=en+p["initial_stop_atr"]*float(r.atr);q=size(cash,en,stp);margin=q*en;efee=margin*fee
            if q>0 and margin+efee<=cash:
                before=cash;cash-=margin+efee;pos={"side":"S","entry":en,"q":q,"margin":margin,"trail":stp,"risk":stp-en,"locked":False,"before":before}
    final=cash
    if pos:
        last=float(d.iloc[-1].close)
        final += pos["q"]*last*(1-fee) if pos["side"]=="L" else pos["margin"]+(pos["entry"]-last)*pos["q"]-pos["q"]*last*fee
    t=pd.DataFrame(tr,columns=["Datum","Richting","Entry","Exit","Resultaat €","Reden"])
    c=pd.DataFrame(curve,columns=["timestamp","equity"]).set_index("timestamp")
    pn=t["Resultaat €"].tolist() if not t.empty else [];w=[x for x in pn if x>0];lo=[x for x in pn if x<0]
    gp=sum(w);gl=abs(sum(lo));pf=gp/gl if gl else (math.inf if gp else 0)
    aw=np.mean(w) if w else 0;al=np.mean(lo) if lo else 0;pay=aw/abs(al) if al<0 else (math.inf if aw else 0)
    dd=float((c.equity/c.equity.cummax()-1).min()*100) if not c.empty else 0
    m={"final":final,"return":(final/cash0-1)*100,"trades":len(t),"winrate":len(w)/len(t)*100 if len(t) else 0,"pf":pf,"dd":dd,
       "avgwin":aw,"avgloss":al,"payoff":pay,"expectancy":np.mean(pn) if pn else 0,
       "longs":int((t.Richting=="LONG").sum()) if not t.empty else 0,"shorts":int((t.Richting=="SHORT").sum()) if not t.empty else 0}
    return m,t,c

def status(m):
    if m["trades"]<10:return "⚪ Te weinig trades"
    if m["return"]>0 and m["pf"]>=1.5 and m["dd"]>-10:return "🟢 Interessant voor verdere paper testing"
    if m["return"]>0 and m["pf"]>1:return "🟡 Positief, verder testen"
    return "🔴 Niet geschikt voor live"

st.title("📈 AI Trend Trader v0.5")
st.caption("Marktprofielen • multi-timeframe filter • ADX • automatische vergelijking")
st.success("🔒 Alleen backtest/paper testing — echte orders staan uit.")

market=st.selectbox("Markt",list(ASSETS))
label=st.selectbox("Instrument",list(ASSETS[market]))
ticker=ASSETS[market][label];profile=CFG["profiles"][pname(market,label)]
cash=st.number_input("Fictief startkapitaal (€)",min_value=500.0,value=5000.0,step=500.0)
st.info(f"Actief profiel: **{pname(market,label).upper()}**")

a,b=st.tabs(["Eén test","Automatisch vergelijken"])
with a:
    tl=st.selectbox("Tijdsframe",["1 uur","4 uur","1 dag"],index=2);tf={"1 uur":"1h","4 uur":"4h","1 dag":"1d"}[tl]
    shorts=st.toggle("Short-posities testen",value=bool(profile["allow_short_default"]))
    if st.button("▶️ Start verbeterde backtest",type="primary"):
        try:
            with st.spinner("Test uitvoeren..."):
                m,t,c=backtest(get_data(market,ticker,tf),cash,market,label,tf,shorts)
                st.session_state["single"]=(m,t,c)
        except Exception as e: st.error(str(e))
    if "single" in st.session_state:
        m,t,c=st.session_state["single"];st.subheader(status(m))
        x,y=st.columns(2);x.metric("Eindwaarde",f"€{m['final']:,.2f}");y.metric("Rendement",f"{m['return']:.2f}%")
        x,y=st.columns(2);x.metric("Winrate",f"{m['winrate']:.1f}%");y.metric("Max. drawdown",f"{m['dd']:.2f}%")
        x,y=st.columns(2);x.metric("Profit factor","∞" if math.isinf(m["pf"]) else f"{m['pf']:.2f}");y.metric("Trades",m["trades"])
        x,y=st.columns(2);x.metric("Gem. winnaar",f"€{m['avgwin']:.2f}");y.metric("Gem. verliezer",f"€{m['avgloss']:.2f}")
        x,y=st.columns(2);x.metric("Payoff ratio","∞" if math.isinf(m["payoff"]) else f"{m['payoff']:.2f}");y.metric("Expectancy/trade",f"€{m['expectancy']:.2f}")
        st.caption(f"Longs: {m['longs']} · Shorts: {m['shorts']}")
        if not c.empty: st.line_chart(c.equity)
        if not t.empty:
            with st.expander("Trades bekijken"): st.dataframe(t,use_container_width=True,hide_index=True)

with b:
    st.write("Test automatisch 1 uur, 4 uur en 1 dag — telkens zonder én met shorts.")
    if st.button("🧪 Test alle 6 combinaties",type="primary"):
        rows=[];bar=st.progress(0);comb=[("1h","1 uur",False),("1h","1 uur",True),("4h","4 uur",False),("4h","4 uur",True),("1d","1 dag",False),("1d","1 dag",True)]
        for i,(tf,lab,sh) in enumerate(comb,1):
            try:
                m,_,_=backtest(get_data(market,ticker,tf),cash,market,label,tf,sh)
                rows.append({"Tijdsframe":lab,"Shorts":"Aan" if sh else "Uit","Rendement %":round(m["return"],2),"PF":round(m["pf"],2) if not math.isinf(m["pf"]) else 999,
                             "DD %":round(m["dd"],2),"Winrate %":round(m["winrate"],1),"Trades":m["trades"],"Gem winnaar €":round(m["avgwin"],2),
                             "Gem verliezer €":round(m["avgloss"],2),"Expectancy €/trade":round(m["expectancy"],2),"Status":status(m)})
            except Exception as e: rows.append({"Tijdsframe":lab,"Shorts":"Aan" if sh else "Uit","Status":f"Fout: {e}"})
            bar.progress(i/6)
        st.session_state["cmp"]=pd.DataFrame(rows)
    if "cmp" in st.session_state:
        st.dataframe(st.session_state["cmp"],use_container_width=True,hide_index=True)

st.divider()
st.write("Nieuw in v0.5: aparte marktprofielen, multi-timeframe regimefilter, ADX, long-bias voor aandelen/ETF's/indices, strengere crypto-filtering, betere trailing stops en automatische vergelijking.")
st.warning("Een backtest is geen winstgarantie. Deze versie blijft uitsluitend voor onderzoek/paper testing.")
