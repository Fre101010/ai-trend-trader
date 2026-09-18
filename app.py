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



def validation_metrics(m,c):
    sharpe=sortino=0.0
    if c is not None and not c.empty and len(c)>3:
        ret=c.equity.pct_change().dropna()
        if len(ret)>2 and ret.std()>0:
            sharpe=float(ret.mean()/ret.std()*np.sqrt(252))
        downside=ret[ret<0]
        if len(downside)>1 and downside.std()>0:
            sortino=float(ret.mean()/downside.std()*np.sqrt(252))
    out=dict(m);out['sharpe']=sharpe;out['sortino']=sortino
    return out

def buy_hold_return(d):
    d=d.dropna(subset=['close'])
    return 0.0 if len(d)<2 else float((d.close.iloc[-1]/d.close.iloc[0]-1)*100)

def validate_daily(market,label,ticker,cash,shorts):
    d=get_data(market,ticker,'1d').copy()
    cut=max(300,int(len(d)*0.70))
    train=d.iloc[:cut].copy()
    test=d.iloc[max(0,cut-250):].copy()
    full_m,_,full_c=backtest(d,cash,market,label,'1d',shorts)
    train_m,_,train_c=backtest(train,cash,market,label,'1d',shorts)
    test_m,_,test_c=backtest(test,cash,market,label,'1d',shorts)
    return d,validation_metrics(full_m,full_c),validation_metrics(train_m,train_c),validation_metrics(test_m,test_c),full_c

def walk_forward_daily(d,market,label,cash,shorts,folds=4):
    rows=[]
    if len(d)<900:return pd.DataFrame()
    warm=250
    usable=len(d)-warm
    step=max(150,usable//(folds+2))
    for k in range(folds):
        test_start=warm+step*(k+1)
        test_end=min(len(d),test_start+step)
        if test_end-test_start<90:break
        seg=d.iloc[max(0,test_start-warm):test_end].copy()
        m,_,_=backtest(seg,cash,market,label,'1d',shorts)
        rows.append({'Fold':k+1,'Start':str(d.index[test_start].date()),'Einde':str(d.index[test_end-1].date()),
                     'Rendement %':round(m['return'],2),'PF':round(m['pf'],2) if not math.isinf(m['pf']) else 999,
                     'DD %':round(m['dd'],2),'Trades':m['trades']})
    return pd.DataFrame(rows)

def yearly_daily(d,market,label,cash,shorts):
    rows=[]
    for y in sorted(set(d.index.year)):
        year=d[d.index.year==y]
        if len(year)<80:continue
        start=d.index.get_indexer([year.index[0]])[0]
        seg=d.iloc[max(0,start-250):d.index.get_indexer([year.index[-1]])[0]+1].copy()
        m,_,_=backtest(seg,cash,market,label,'1d',shorts)
        rows.append({'Jaar':int(y),'Rendement %':round(m['return'],2),'PF':round(m['pf'],2) if not math.isinf(m['pf']) else 999,'Trades':m['trades']})
    return pd.DataFrame(rows)

def scan_one(market,label,ticker):
    profile=CFG['profiles'][pname(market,label)]
    frames={}
    for tf in ['1d','4h','1h']:
        d=get_data(market,ticker,tf)
        e=enrich(d,profile)
        r=e.iloc[-1]
        L,S=scores(r,market)
        trend='BULLISH' if L>S and bool(r.bullreg) else ('BEARISH' if S>L and bool(r.bearreg) else 'NEUTRAAL')
        frames[tf]={'trend':trend,'adx':float(r.adx),'price':float(r.close),'atr':float(r.atr),'L':L,'S':S}
    if frames['1d']['trend']=='BULLISH' and frames['4h']['trend']=='BULLISH':
        action='LONG / HOLD' if frames['1h']['trend']!='BEARISH' else 'WACHT OP PULLBACK'
    elif frames['1d']['trend']=='BEARISH' and frames['4h']['trend']=='BEARISH':
        action='CASH' if market in ["Aandelen","ETF's","Indices"] or label=='Goud' else 'SHORT-KANDIDAAT'
    else:
        action='CASH / WACHTEN'
    return frames,action


st.title("📈 AI Trend Trader v0.6")
st.caption("Validatie • out-of-sample • walk-forward • echte 1D/4H/1H scanner • paper portfolio")
st.success("🔒 Geen echte orders. Alles blijft backtest/paper trading.")

core=[("Grondstoffen","Goud","GC=F"),("ETF's","Nasdaq 100 ETF","QQQ"),("ETF's","S&P 500 ETF","SPY"),("Aandelen","Apple","AAPL")]

t1,t2,t3=st.tabs(["1. Validatie","2. Markt scanner","3. Paper portfolio"])

with t1:
    st.subheader("Professionele validatie")
    market=st.selectbox("Markt",list(ASSETS),key='vm')
    label=st.selectbox("Instrument",list(ASSETS[market]),key='vl')
    ticker=ASSETS[market][label]
    cash=st.number_input("Fictief startkapitaal (€)",min_value=500.0,value=5000.0,step=500.0,key='vc')
    shorts=st.toggle("Shorts meenemen",value=False,key='vs')
    if st.button("🧪 Start professionele validatie",type="primary"):
        try:
            with st.spinner("Dagdata testen, out-of-sample en walk-forward berekenen..."):
                d,full_m,train_m,test_m,curve=validate_daily(market,label,ticker,cash,shorts)
                wf=walk_forward_daily(d,market,label,cash,shorts)
                yr=yearly_daily(d,market,label,cash,shorts)
                st.session_state['val']=(market,label,d,full_m,train_m,test_m,curve,wf,yr,buy_hold_return(d))
        except Exception as e: st.error(str(e))
    if 'val' in st.session_state:
        market,label,d,full_m,train_m,test_m,curve,wf,yr,bh=st.session_state['val']
        st.write(f"**{label}** · {d.index[0].date()} t/m {d.index[-1].date()} · {len(d)} dagcandles")
        a,b=st.columns(2);a.metric("Volledige strategie",f"{full_m['return']:.2f}%");b.metric("Buy & hold",f"{bh:.2f}%")
        a,b=st.columns(2);a.metric("Train 70%",f"{train_m['return']:.2f}%");b.metric("Out-of-sample 30%",f"{test_m['return']:.2f}%")
        a,b=st.columns(2);a.metric("Test PF","∞" if math.isinf(test_m['pf']) else f"{test_m['pf']:.2f}");b.metric("Test drawdown",f"{test_m['dd']:.2f}%")
        a,b=st.columns(2);a.metric("Sharpe",f"{full_m['sharpe']:.2f}");b.metric("Sortino",f"{full_m['sortino']:.2f}")
        if test_m['return']>0 and test_m['pf']>1: st.success("Out-of-sample is positief: kandidaat voor verdere paper testing.")
        else: st.warning("Out-of-sample is niet overtuigend positief: niet promoveren naar live trading.")
        st.markdown("#### Walk-forward")
        st.dataframe(wf,use_container_width=True,hide_index=True) if not wf.empty else st.info("Te weinig data voor meerdere folds.")
        st.markdown("#### Jaar per jaar")
        st.dataframe(yr,use_container_width=True,hide_index=True)
        if curve is not None and not curve.empty:
            st.markdown("#### Equity curve")
            st.line_chart(curve.equity)

with t2:
    st.subheader("Actuele 1D / 4H / 1H scanner")
    st.write("1D bepaalt de hoofdrichting, 4H bevestigt en 1H helpt de timing.")
    if st.button("🔎 Scan kernportfolio",type="primary"):
        rows=[];details={};bar=st.progress(0)
        for i,(market,label,ticker) in enumerate(core,1):
            try:
                frames,action=scan_one(market,label,ticker)
                details[label]=frames
                rows.append({'Markt':label,'1D':frames['1d']['trend'],'4H':frames['4h']['trend'],'1H':frames['1h']['trend'],'ADX 1D':round(frames['1d']['adx'],1),'Actie':action})
            except Exception as e:
                rows.append({'Markt':label,'Actie':f'Fout: {e}'})
            bar.progress(i/len(core))
        st.session_state['scan']=pd.DataFrame(rows)
    if 'scan' in st.session_state:
        st.dataframe(st.session_state['scan'],use_container_width=True,hide_index=True)
        st.caption("Signalen op actuele data; geen winstgarantie.")

with t3:
    st.subheader("Paper portfolio snapshot")
    st.write("Deze versie ververst wanneer je de app opent of op de knop drukt. Streamlit Community Cloud is geen 24/7 achtergrondserver.")
    paper_cash=st.number_input("Virtueel portefeuillekapitaal (€)",min_value=500.0,value=5000.0,step=500.0,key='pc')
    selected=st.multiselect("Markten",[x[1] for x in core],default=[x[1] for x in core])
    if st.button("📋 Update paper portfolio",type="primary"):
        rows=[]
        lookup={label:(market,ticker) for market,label,ticker in core}
        for label in selected:
            market,ticker=lookup[label]
            try:
                frames,action=scan_one(market,label,ticker)
                price=frames['1d']['price'];atrv=frames['1d']['atr'];profile=CFG['profiles'][pname(market,label)]
                if action=='LONG / HOLD' and np.isfinite(price) and np.isfinite(atrv) and atrv>0:
                    stop=price-profile['initial_stop_atr']*atrv
                    qty=size(paper_cash/max(1,len(selected)),price,stop)
                    value=qty*price;state='PAPER LONG'
                else:
                    stop=np.nan;value=0;state='CASH'
                rows.append({'Markt':label,'Status':state,'Actie':action,'Koers':round(price,2),'Indicatieve stop':round(stop,2) if np.isfinite(stop) else None,'Positiewaarde €':round(value,2),'1D':frames['1d']['trend'],'4H':frames['4h']['trend'],'1H':frames['1h']['trend']})
            except Exception as e:
                rows.append({'Markt':label,'Status':'FOUT','Actie':str(e)})
        st.session_state['paper']=pd.DataFrame(rows)
    if 'paper' in st.session_state:
        st.dataframe(st.session_state['paper'],use_container_width=True,hide_index=True)
        st.info("Voor echte 24/7 paper trading voegen we later een externe database + scheduler toe.")

st.divider()
st.write("Kernregel: geen live trading op basis van één mooie backtest. Eerst out-of-sample, walk-forward en actuele paper tracking.")
