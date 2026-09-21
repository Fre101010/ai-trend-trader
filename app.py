import pandas as pd
import streamlit as st
from trading_core import CFG, fetch, market_snapshot, desired_action
from storage import load_state, save_state, get_secret
from paper_runner import run_once
from analytics import marked_values, trade_stats, max_drawdown_pct, total_state_equity

st.set_page_config(page_title="AI Trend Trader v2.0",page_icon="📈",layout="wide")

st.markdown("""<style>
.stApp{background:linear-gradient(180deg,#eef5fb 0,#f8fbff 230px,#fff 700px)}
.block-container{max-width:1500px;padding-top:1rem;padding-bottom:4rem}
.hero{background:linear-gradient(135deg,#fff,#edf6ff);border:1px solid #dfeaf4;border-radius:22px;padding:22px 24px;box-shadow:0 10px 30px rgba(25,60,95,.07);margin-bottom:14px}
.hero h1{margin:0;color:#102a49;font-size:2.4rem}.hero p{color:#70859b;margin:.4rem 0 0}
.pills{display:flex;gap:8px;flex-wrap:wrap;margin-top:13px}.pill{padding:7px 10px;border-radius:999px;font-size:.78rem;font-weight:700;background:#eef6ff;color:#2864a8}.pill.green{background:#ecf9f2;color:#137d52}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:12px 0 16px}
.card{background:#fff;border:1px solid #e3ecf4;border-radius:17px;padding:15px;box-shadow:0 6px 22px rgba(30,65,100,.06)}
.card .lbl{font-size:.77rem;color:#718397;font-weight:700}.card .val{font-size:1.55rem;color:#102a49;font-weight:850;margin-top:7px}
.card .sub{font-size:.72rem;color:#8392a2;margin-top:5px}
.portfolio-head{font-size:1.25rem;font-weight:850;color:#173755;margin-top:10px}
.section-sub{font-size:.84rem;color:#7a8c9e;margin-bottom:10px}
[data-testid="stDataFrame"]{border:1px solid #e3ecf4;border-radius:15px;overflow:hidden}
.stButton>button{width:100%;border-radius:12px;min-height:45px;font-weight:750}
@media(max-width:900px){.cards{grid-template-columns:repeat(2,1fr)}}
</style>""",unsafe_allow_html=True)

state,mode=load_state()

st.markdown("""
<div class="hero">
<h1>📊 AI Trend Trader v2.0</h1>
<p>Twee aparte strategieportefeuilles: Swing voor langere trends en Active voor kortere trades.</p>
<div class="pills"><span class="pill green">🛡️ PAPER ONLY</span><span class="pill green">💾 Supabase actief</span><span class="pill">🔔 Telegram actief</span><span class="pill">Swing + Active</span></div>
</div>
""",unsafe_allow_html=True)

def live_prices_for(p, mode):
    prices={}
    tf="1h" if mode=="swing" else "15m"
    for asset in p.get("positions",{}):
        try:
            prices[asset]=float(fetch(CFG["portfolio"]["assets"][asset]["ticker"],tf)["close"].iloc[-1])
        except Exception:
            pass
    return prices

def portfolio_cards(p, mode):
    marks=marked_values(p,live_prices_for(p,mode))
    stats=trade_stats(p); dd=max_drawdown_pct(p)
    start=float(p.get("automation",{}).get("account_capital",0) or 0)
    html='<div class="cards">'
    for lbl,val,sub in [
        ("Equity",f"€{marks['equity']:,.2f}",mode.upper()),
        ("Cash",f"€{marks['cash']:,.2f}","Vrij beschikbaar"),
        ("Open P/L",f"€{marks['open_pnl']:,.2f}","Niet gerealiseerd"),
        ("Gerealiseerde P/L",f"€{marks['realized_pnl']:,.2f}","Gesloten trades"),
        ("Open posities",str(len(p.get("positions",{}))),"Actief"),
        ("Gesloten trades",str(stats["count"]),"Historiek"),
        ("Winrate",f"{stats['winrate']:.1f}%","Forward test"),
        ("Max drawdown",f"{dd:.2f}%","Risico"),
    ]:
        html+=f'<div class="card"><div class="lbl">{lbl}</div><div class="val">{val}</div><div class="sub">{sub}</div></div>'
    html+='</div>'
    st.markdown(html,unsafe_allow_html=True)
    return marks

tabs=st.tabs(["Overzicht","Swing Portfolio","Active Portfolio","Transfer","Instrumenten","Scanner","Historiek"])

with tabs[0]:
    sw=marked_values(state["portfolios"]["swing"],live_prices_for(state["portfolios"]["swing"],"swing"))
    ac=marked_values(state["portfolios"]["active"],live_prices_for(state["portfolios"]["active"],"active"))
    total=sw["equity"]+ac["equity"]
    st.markdown('<div class="portfolio-head">Totaal vermogen</div><div class="section-sub">Gecombineerde waarde van Swing + Active.</div>',unsafe_allow_html=True)
    html='<div class="cards">'
    for lbl,val,sub in [
        ("Totale equity",f"€{total:,.2f}","Swing + Active"),
        ("Swing equity",f"€{sw['equity']:,.2f}","Langere termijn"),
        ("Active equity",f"€{ac['equity']:,.2f}","Kortere termijn"),
        ("Totale open P/L",f"€{sw['open_pnl']+ac['open_pnl']:,.2f}","Beide portefeuilles"),
    ]:
        html+=f'<div class="card"><div class="lbl">{lbl}</div><div class="val">{val}</div><div class="sub">{sub}</div></div>'
    html+='</div>'
    st.markdown(html,unsafe_allow_html=True)

    if st.button("▶️ Beide portefeuilles nu bijwerken",type="primary"):
        with st.spinner("Swing en Active analyseren..."):
            state,mode=run_once()
        st.success("Beide portefeuilles bijgewerkt.")

with tabs[1]:
    p=state["portfolios"]["swing"]
    st.markdown('<div class="portfolio-head">Swing Portfolio</div><div class="section-sub">1D / 4H / 1H — minder trades, langere trendposities.</div>',unsafe_allow_html=True)
    marks=portfolio_cards(p,"swing")
    rows=[]
    prices=live_prices_for(p,"swing")
    for a,pos in p.get("positions",{}).items():
        px=prices.get(a,pos.get("last_price",pos["entry"])); qty=float(pos["qty"])
        rows.append({"Markt":a,"Status":"LONG","Entry":round(pos["entry"],2),"Laatste koers":round(px,2),"Trailing stop":round(pos["trail_stop"],2),"Open P/L €":round((px-pos["entry"])*qty,2)})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

with tabs[2]:
    p=state["portfolios"]["active"]
    st.markdown('<div class="portfolio-head">Active Portfolio</div><div class="section-sub">4H / 1H / 15m — meer signalen, kortere trades.</div>',unsafe_allow_html=True)
    marks=portfolio_cards(p,"active")
    rows=[]
    prices=live_prices_for(p,"active")
    for a,pos in p.get("positions",{}).items():
        px=prices.get(a,pos.get("last_price",pos["entry"])); qty=float(pos["qty"])
        rows.append({"Markt":a,"Status":"LONG","Entry":round(pos["entry"],2),"Laatste koers":round(px,2),"Trailing stop":round(pos["trail_stop"],2),"Open P/L €":round((px-pos["entry"])*qty,2)})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

with tabs[3]:
    st.markdown('<div class="portfolio-head">Interne transfer</div><div class="section-sub">Verplaats alleen vrije cash tussen Swing en Active. Open posities worden nooit aangeraakt.</div>',unsafe_allow_html=True)
    direction=st.selectbox("Van → Naar",["Swing → Active","Active → Swing"])
    source="swing" if direction.startswith("Swing") else "active"
    target="active" if source=="swing" else "swing"
    available=float(state["portfolios"][source].get("cash",0))
    st.info(f"Vrije cash in {source.title()}: €{available:,.2f}")
    amount=st.number_input("Bedrag (€)",min_value=0.0,max_value=max(0.0,available),value=0.0,step=50.0)
    if st.button("💸 Transfer uitvoeren",type="primary"):
        if amount<=0:
            st.warning("Kies een bedrag groter dan €0.")
        elif amount>available:
            st.error("Onvoldoende vrije cash.")
        else:
            state["portfolios"][source]["cash"]-=amount
            state["portfolios"][target]["cash"]+=amount
            state["transfers"].append({"time":pd.Timestamp.utcnow().isoformat(),"from":source,"to":target,"amount":amount})
            save_state(state,update_last_run=False)
            st.success(f"€{amount:,.2f} overgezet van {source.title()} naar {target.title()}.")

    if state.get("transfers"):
        st.dataframe(pd.DataFrame(state["transfers"][-50:][::-1]),use_container_width=True,hide_index=True)

with tabs[4]:
    st.markdown('<div class="portfolio-head">Instrumenten per portefeuille</div><div class="section-sub">Je kunt dezelfde markt in Swing, Active of beide laten traden.</div>',unsafe_allow_html=True)
    for pid,label in [("swing","Swing"),("active","Active")]:
        st.markdown(f"### {label}")
        p=state["portfolios"][pid]
        enabled=p.setdefault("enabled_assets",{})
        cols=st.columns(2)
        for i,a in enumerate(CFG["portfolio"]["assets"]):
            enabled.setdefault(a,True)
            enabled[a]=cols[i%2].toggle(a,value=enabled[a],key=f"{pid}_{a}")
        if st.button(f"💾 {label} instrumenten opslaan",key=f"save_{pid}"):
            p["enabled_assets"]=enabled
            save_state(state,update_last_run=False)
            st.success(f"{label} instrumenten opgeslagen.")

with tabs[5]:
    portfolio=st.radio("Scanner voor",["Swing","Active"],horizontal=True)
    mode_sel=portfolio.lower()
    out=[]
    if st.button("🔎 Scan markten",type="primary"):
        for a in CFG["portfolio"]["assets"]:
            s=market_snapshot(a,mode_sel); act=desired_action(a,s,mode_sel)
            if mode_sel=="swing":
                out.append({"Markt":a,"1D":s["1d"]["trend"],"4H":s["4h"]["trend"],"1H":s["1h"]["trend"],"Actie":act})
            else:
                out.append({"Markt":a,"4H":s["4h"]["trend"],"1H":s["1h"]["trend"],"15m":s["15m"]["trend"],"Actie":act})
        st.session_state["scan_v2"]=pd.DataFrame(out)
    if "scan_v2" in st.session_state:
        st.dataframe(st.session_state["scan_v2"],use_container_width=True,hide_index=True)

with tabs[6]:
    which=st.selectbox("Portfolio",["Swing","Active"])
    p=state["portfolios"][which.lower()]
    st.markdown("### Gesloten trades")
    if p.get("trades"):
        st.dataframe(pd.DataFrame(p["trades"])[::-1],use_container_width=True,hide_index=True)
    else:
        st.info("Nog geen gesloten trades.")
