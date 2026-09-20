import pandas as pd
import streamlit as st
from trading_core import CFG, market_snapshot, desired_action
from storage import load_state, get_secret
from paper_runner import run_once
from notifier import notify

st.set_page_config(page_title="AI Trend Trader v0.8",page_icon="📈",layout="centered")
st.markdown("""<style>
.block-container{padding-top:1rem;padding-bottom:4rem;max-width:980px}
.stButton>button{width:100%;min-height:52px;border-radius:14px;font-weight:700}
div[data-testid="stMetric"]{border:1px solid rgba(128,128,128,.25);border-radius:16px;padding:12px}
</style>""",unsafe_allow_html=True)

st.title("📈 AI Trend Trader v0.8")
st.caption("Persistente paper trading • alerts • events • Goud • Nasdaq 100 ETF • S&P 500 ETF")
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

tabs=st.tabs(["Dashboard","Live scanner","Events","Tradehistoriek","Meldingen"])

with tabs[0]:
    if st.button("▶️ Update paper portfolio nu",type="primary"):
        with st.spinner("Markten scannen en paper portfolio bijwerken..."):
            state,mode=run_once()
        st.success("Paper portfolio bijgewerkt.")
    state,_=load_state()
    positions=state.get("positions",{})
    trades=state.get("trades",[])
    hist=state.get("equity_history",[])
    equity=state.get("cash",0)
    for asset,pos in positions.items():
        equity += pos.get("qty",0)*pos.get("last_price",pos.get("entry",0))

    a,b=st.columns(2)
    a.metric("Paper cash",f"€{state.get('cash',0):,.2f}")
    b.metric("Geschatte equity",f"€{equity:,.2f}")
    a,b=st.columns(2)
    a.metric("Open posities",len(positions))
    b.metric("Gesloten trades",len(trades))
    st.caption(f"Laatste run: {state.get('last_run') or 'nog niet uitgevoerd'}")

    rows=[]
    for asset in CFG["portfolio"]["assets"]:
        pos=positions.get(asset)
        if pos:
            open_pct=((pos.get("last_price",pos["entry"])-pos["entry"])/pos["entry"])*100
            rows.append({
                "Markt":asset,"Status":"LONG","Entry":round(pos["entry"],2),
                "Laatste koers":round(pos.get("last_price",0),2),
                "Trailing stop":round(pos.get("trail_stop",0),2),
                "Open P/L €":round(pos.get("unrealized_pnl",0),2),
                "Open P/L %":round(open_pct,2)
            })
        else:
            rows.append({"Markt":asset,"Status":"CASH","Entry":None,"Laatste koers":None,"Trailing stop":None,"Open P/L €":0,"Open P/L %":0})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

    if hist:
        h=pd.DataFrame(hist)
        h["time"]=pd.to_datetime(h["time"])
        h=h.set_index("time")
        st.markdown("#### Paper equity curve")
        st.line_chart(h["equity"])

with tabs[1]:
    if st.button("🔎 Scan 1D / 4H / 1H",type="primary"):
        out=[]
        assets=list(CFG["portfolio"]["assets"].keys())
        bar=st.progress(0)
        for i,asset in enumerate(assets,1):
            snap=market_snapshot(asset)
            out.append({"Markt":asset,"1D":snap["1d"]["trend"],"4H":snap["4h"]["trend"],"1H":snap["1h"]["trend"],"ADX 1D":round(snap["1d"]["adx"],1),"Actie":desired_action(asset,snap)})
            bar.progress(i/len(assets))
        st.session_state["scan"]=pd.DataFrame(out)
    if "scan" in st.session_state:
        st.dataframe(st.session_state["scan"],use_container_width=True,hide_index=True)

with tabs[2]:
    state,_=load_state()
    events=state.get("events",[])
    if not events:
        st.info("Nog geen events.")
    else:
        e=pd.DataFrame(events)
        e["time"]=pd.to_datetime(e["time"])
        e=e.sort_values("time",ascending=False)
        st.dataframe(e[["time","kind","asset","message"]],use_container_width=True,hide_index=True)

with tabs[3]:
    state,_=load_state()
    trades=state.get("trades",[])
    if not trades:
        st.info("Nog geen gesloten paper trades.")
    else:
        t=pd.DataFrame(trades)
        st.dataframe(t,use_container_width=True,hide_index=True)
        st.metric("Totaal gerealiseerde paper P/L",f"€{t['pnl'].sum():,.2f}")
        st.metric("Winrate",f"{(t['pnl']>0).mean()*100:.1f}%")

with tabs[4]:
    st.write("Meldingen worden verstuurd bij nieuwe PAPER LONG, betekenisvolle verhoging van de trailing stop en PAPER EXIT.")
    if telegram_ready or discord_ready:
        if st.button("🔔 Stuur testmelding"):
            ok,target=notify("✅ AI Trend Trader v0.8 testmelding — notificaties werken.")
            if ok:
                st.success(f"Testmelding verstuurd via {target}.")
            else:
                st.error(f"Melding kon niet worden verstuurd: {target}")
    else:
        st.warning("Nog geen notificatie-secrets ingesteld.")
        st.code('TELEGRAM_BOT_TOKEN="..."\nTELEGRAM_CHAT_ID="..."',language="toml")
