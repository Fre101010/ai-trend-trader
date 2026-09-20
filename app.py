import pandas as pd
import streamlit as st
from trading_core import CFG, market_snapshot, desired_action, action_details
from storage import load_state, get_secret
from paper_runner import run_once
from notifier import notify
from analytics import (
    current_equity, realized_pnl, open_pnl, trade_stats,
    max_drawdown_pct, return_since_start_pct, per_market_stats
)

st.set_page_config(page_title="AI Trend Trader v1.0.1",page_icon="📈",layout="wide")
st.markdown("""<style>
.block-container{padding-top:1rem;padding-bottom:4rem;max-width:1180px}
.stButton>button{width:100%;min-height:48px;border-radius:14px;font-weight:700}
div[data-testid="stMetric"]{border:1px solid rgba(128,128,128,.25);border-radius:16px;padding:12px}
</style>""",unsafe_allow_html=True)

st.title("📈 AI Trend Trader v1.0.1")
st.caption("Persistente paper trading • BTC & ETH 24/7 • alerts • performance analytics • dagelijkse Telegram-samenvatting")
st.success("🔒 PAPER ONLY — geen echte orders of brokerkoppeling.")

state,mode=load_state()
if mode=="supabase":
    st.success("💾 Persistente opslag actief via Supabase")
elif str(mode).startswith("supabase-error"):
    st.error("💾 Supabase is gevonden, maar de verbinding geeft nog een fout.")
else:
    st.warning("💾 Demo-opslag actief. Koppel Supabase voor echte persistentie.")

telegram_ready = bool(get_secret("TELEGRAM_BOT_TOKEN") and get_secret("TELEGRAM_CHAT_ID"))
discord_ready = bool(get_secret("DISCORD_WEBHOOK_URL"))
if telegram_ready:
    st.info("🔔 Telegram-meldingen actief")
elif discord_ready:
    st.info("🔔 Discord-meldingen actief")
else:
    st.info("🔕 Meldingen nog niet gekoppeld. Paper trading blijft wel werken.")

tabs=st.tabs(["Dashboard","Performance","Live scanner","Events","Tradehistoriek","Meldingen"])

with tabs[0]:
    if st.button("▶️ Update paper portfolio nu",type="primary"):
        with st.spinner("Markten scannen en paper portfolio bijwerken..."):
            state,mode=run_once()
        st.success("Paper portfolio bijgewerkt.")

    state,_=load_state()
    positions=state.get("positions",{})
    trades=state.get("trades",[])
    hist=state.get("equity_history",[])
    eq=current_equity(state)

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Equity",f"€{eq:,.2f}",f"{return_since_start_pct(state):+.2f}%")
    c2.metric("Paper cash",f"€{state.get('cash',0):,.2f}")
    c3.metric("Open P/L",f"€{open_pnl(state):,.2f}")
    c4.metric("Gerealiseerd P/L",f"€{realized_pnl(state):,.2f}")

    c1,c2,c3,c4=st.columns(4)
    stats=trade_stats(state)
    pf=stats["profit_factor"]
    pf_text="∞" if pf==float("inf") else f"{pf:.2f}"
    c1.metric("Open posities",len(positions))
    c2.metric("Gesloten trades",stats["count"])
    c3.metric("Winrate",f"{stats['winrate']:.1f}%")
    c4.metric("Max drawdown",f"{max_drawdown_pct(state):.2f}%")

    st.caption(f"Laatste run: {state.get('last_run') or 'nog niet uitgevoerd'}")

    rows=[]
    for asset in CFG["portfolio"]["assets"]:
        pos=positions.get(asset)
        if pos:
            last_price=pos.get("last_price",pos["entry"])
            qty=float(pos.get("qty",0))
            open_pnl_eur=(last_price-pos["entry"])*qty
            open_pct=((last_price-pos["entry"])/pos["entry"])*100
            stop_distance=((last_price-pos.get("trail_stop",0))/last_price)*100 if last_price else 0
            rows.append({
                "Markt":asset,"Status":"LONG","Entry":round(pos["entry"],2),
                "Laatste koers":round(last_price,2),
                "Trailing stop":round(pos.get("trail_stop",0),2),
                "Afstand tot stop %":round(stop_distance,2),
                "Open P/L €":round(open_pnl_eur,2),
                "Open P/L %":round(open_pct,2)
            })
        else:
            rows.append({"Markt":asset,"Status":"CASH","Entry":None,"Laatste koers":None,
                         "Trailing stop":None,"Afstand tot stop %":None,"Open P/L €":0,"Open P/L %":0})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

    if hist:
        h=pd.DataFrame(hist)
        h["time"]=pd.to_datetime(h["time"])
        h=h.set_index("time")
        st.markdown("#### Paper equity curve")
        st.line_chart(h["equity"])

with tabs[1]:
    state,_=load_state()
    stats=trade_stats(state)
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Rendement sinds start",f"{return_since_start_pct(state):+.2f}%")
    c2.metric("Profit factor","∞" if stats["profit_factor"]==float("inf") else f"{stats['profit_factor']:.2f}")
    c3.metric("Gemiddelde trade",f"€{stats['avg_trade']:.2f}")
    c4.metric("Max drawdown",f"{max_drawdown_pct(state):.2f}%")

    c1,c2,c3=st.columns(3)
    c1.metric("Beste trade",f"€{stats['best_trade']:.2f}")
    c2.metric("Slechtste trade",f"€{stats['worst_trade']:.2f}")
    c3.metric("Winrate",f"{stats['winrate']:.1f}%")

    market_stats=per_market_stats(state)
    if market_stats:
        df=pd.DataFrame([
            {"Markt":a,"Trades":m["trades"],"P/L €":round(m["pnl"],2),"Winrate %":round(m["winrate"],1)}
            for a,m in market_stats.items()
        ])
        st.markdown("#### Resultaten per markt")
        st.dataframe(df,use_container_width=True,hide_index=True)
    else:
        st.info("Nog geen gesloten trades om per markt te analyseren.")

with tabs[2]:
    if st.button("🔎 Scan 1D / 4H / 1H",type="primary"):
        out=[]
        assets=list(CFG["portfolio"]["assets"].keys())
        bar=st.progress(0)
        for i,asset in enumerate(assets,1):
            snap=market_snapshot(asset)
            detail=action_details(asset,snap)
            out.append({
                "Markt":asset,
                "1D":snap["1d"]["trend"],
                "4H":snap["4h"]["trend"],
                "1H":snap["1h"]["trend"],
                "ADX 1D":round(snap["1d"]["adx"],1),
                "RSI 1H":round(snap["1h"]["rsi"],1),
                "Actie":detail["action"],
                "Waarom":detail["reason"]
            })
            bar.progress(i/len(assets))
        st.session_state["scan"]=pd.DataFrame(out)
    if "scan" in st.session_state:
        st.dataframe(st.session_state["scan"],use_container_width=True,hide_index=True)
        st.caption("Bij Bitcoin en Ethereum toont ‘Waarom’ exact welke crypto-filter nog niet voldoet.")

with tabs[3]:
    state,_=load_state()
    events=state.get("events",[])
    if not events:
        st.info("Nog geen events.")
    else:
        e=pd.DataFrame(events)
        e["time"]=pd.to_datetime(e["time"])
        e=e.sort_values("time",ascending=False)
        kinds=["Alle"]+sorted(e["kind"].dropna().unique().tolist())
        selected=st.selectbox("Filter eventtype",kinds)
        if selected!="Alle":
            e=e[e["kind"]==selected]
        st.dataframe(e[["time","kind","asset","message"]],use_container_width=True,hide_index=True)

with tabs[4]:
    state,_=load_state()
    trades=state.get("trades",[])
    if not trades:
        st.info("Nog geen gesloten paper trades.")
    else:
        t=pd.DataFrame(trades)
        st.dataframe(t,use_container_width=True,hide_index=True)

with tabs[5]:
    st.write("Automatische meldingen gaan naar Telegram bij PAPER LONG, trailing-stop update en PAPER EXIT.")
    st.write("v0.9 kan daarnaast elke avond één dagelijkse portfolio-samenvatting sturen.")
    if telegram_ready or discord_ready:
        if st.button("🔔 Stuur testmelding"):
            ok,target=notify("✅ AI Trend Trader v1.0.1 testmelding — notificaties werken.")
            if ok:
                st.success(f"Testmelding verstuurd via {target}.")
            else:
                st.error(f"Melding kon niet worden verstuurd: {target}")
    else:
        st.warning("Nog geen notificatie-secrets ingesteld.")
