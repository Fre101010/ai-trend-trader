import pandas as pd
import streamlit as st
from trading_core import CFG, market_snapshot, desired_action, action_details, fetch
from storage import load_state, get_secret, save_state
from paper_runner import run_once
from notifier import notify
from execution import MODES, normalize_automation, broker_status
from risk_guard import suggested_settings, clamp_settings, portfolio_heat_pct, HARD_LIMITS
from analytics import (
    current_equity, realized_pnl, open_pnl, trade_stats,
    max_drawdown_pct, return_since_start_pct, per_market_stats,
    forward_test_table, weekly_summary, marked_portfolio_values
)

st.set_page_config(page_title="AI Trend Trader v1.4",page_icon="📈",layout="wide")
st.markdown("""<style>
:root{
  --nav:#0d2a4a;--nav2:#173f6c;--accent:#2f80ed;--accent2:#5aa2ff;
  --ink:#102a49;--muted:#73869a;--line:#e3ecf4;--green:#18a76f;--red:#ef5a63;
}
.stApp{
  background:
    radial-gradient(circle at 80% 0%, rgba(75,145,225,.14), transparent 28%),
    linear-gradient(180deg,#eef6fd 0,#f8fbfe 240px,#ffffff 760px);
  color:var(--ink);
}
.block-container{max-width:1540px;padding:0.7rem 1.2rem 4rem}
[data-testid="stHeader"]{background:linear-gradient(90deg,var(--nav),var(--nav2));height:3.1rem}
div[data-testid="stTabs"] button{font-weight:700;color:#47627e;padding:.65rem .95rem}
div[data-testid="stTabs"] button[aria-selected="true"]{color:var(--accent);background:#edf5ff;border-radius:10px 10px 0 0;border-bottom:3px solid var(--accent)}
.stButton>button{border-radius:12px;min-height:44px;font-weight:750;border:1px solid #dce8f3}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,#3288ef,#1d6fd6);color:#fff;border:0}
[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:16px;overflow:hidden;box-shadow:0 6px 24px rgba(24,59,95,.06)}

.hero{
  position:relative;overflow:hidden;border-radius:0 0 24px 24px;
  padding:26px 28px 22px;margin:0 -1.2rem 16px;
  background:
    linear-gradient(90deg,rgba(246,251,255,.98),rgba(236,246,255,.92)),
    radial-gradient(circle at 88% 35%, rgba(72,137,216,.18), transparent 34%);
  border-bottom:1px solid #dce8f3;
}
.hero:after{
  content:"";position:absolute;right:-80px;top:-90px;width:470px;height:300px;
  background:linear-gradient(135deg,rgba(120,176,235,.15),rgba(255,255,255,0));
  transform:rotate(-12deg);border-radius:50%;
}
.brand{display:flex;align-items:center;gap:15px;position:relative;z-index:2}
.brand-icon{
  width:54px;height:54px;border-radius:16px;background:linear-gradient(135deg,#2f80ed,#62a6f8);
  color:#fff;display:flex;align-items:flex-end;justify-content:center;gap:3px;padding:10px;
  box-shadow:0 8px 24px rgba(47,128,237,.24)
}
.brand-icon i{display:block;width:6px;background:white;border-radius:4px}
.brand-icon i:nth-child(1){height:15px}.brand-icon i:nth-child(2){height:24px}.brand-icon i:nth-child(3){height:33px}
.hero-title{font-size:2.5rem;font-weight:900;letter-spacing:-.04em;line-height:1;color:#102b4c}
.hero-sub{font-size:1.15rem;color:#54708e;margin-top:5px}
.hero-desc{font-size:.9rem;color:#71859a;margin-top:6px}
.hero-status{display:grid;grid-template-columns:repeat(3,minmax(180px,1fr));gap:12px;margin-top:18px;max-width:760px;position:relative;z-index:2}
.status-card{
  background:rgba(255,255,255,.9);border:1px solid #dfeaf4;border-radius:15px;padding:12px 14px;
  box-shadow:0 7px 24px rgba(30,67,104,.07);display:flex;align-items:center;gap:11px
}
.status-icon{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:18px}
.status-green{background:#eaf9f2;color:#15935f}.status-blue{background:#eaf3ff;color:#2f80ed}
.status-title{font-size:.78rem;font-weight:850;color:#23425f}.status-sub{font-size:.68rem;color:#8292a2;margin-top:2px}

.kpi-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin-bottom:12px}
.kpi{
  background:#fff;border:1px solid #e3edf5;border-radius:17px;padding:15px 16px 13px;
  min-height:118px;box-shadow:0 7px 24px rgba(30,66,102,.06)
}
.kpi-top{display:flex;align-items:center;gap:9px}.kpi-ico{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:17px;background:#edf5ff}
.kpi-label{font-size:.78rem;font-weight:750;color:#59718a}.kpi-value{font-size:1.65rem;font-weight:900;color:#102a49;margin-top:13px}
.kpi-foot{margin-top:7px;font-size:.72rem;color:#8190a0}.negative{color:#e44753!important}.positive{color:#168d60!important}
.spark{height:3px;border-radius:4px;margin-top:9px;background:linear-gradient(90deg,#d6e7fb,#68a8f3)}
.spark.red{background:linear-gradient(90deg,#ffd9dd,#ef5a63)}

.mid-grid{display:grid;grid-template-columns:1.5fr 1fr;gap:14px;margin-top:14px}
.panel{background:#fff;border:1px solid #e3ecf4;border-radius:18px;padding:16px;box-shadow:0 7px 25px rgba(27,61,96,.06)}
.panel-title{font-size:1.12rem;font-weight:850;color:#163653}
.panel-sub{font-size:.78rem;color:#7a8c9d;margin-top:2px}
.quick-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:14px}
.quick{border:1px solid #e3ecf4;border-radius:14px;padding:13px;display:flex;gap:11px;align-items:center;background:#fbfdff}
.quick-ico{width:40px;height:40px;border-radius:12px;background:#edf5ff;display:flex;align-items:center;justify-content:center;font-size:20px}
.quick-title{font-size:.82rem;font-weight:800;color:#21405f}.quick-sub{font-size:.69rem;color:#7d8e9e;margin-top:2px}
.tip{margin-top:12px;padding:11px 12px;border-radius:13px;background:#eef6ff;color:#2a5d93;font-size:.74rem}

.stats-strip{display:grid;grid-template-columns:repeat(5,1fr);gap:0;margin-top:10px;border-top:1px solid #edf2f6}
.statx{padding:10px 12px;border-right:1px solid #edf2f6}.statx:last-child{border-right:0}
.statx-l{font-size:.68rem;color:#7d8c9c}.statx-v{font-size:.9rem;font-weight:800;color:#193a5b;margin-top:3px}

.section-head{display:flex;justify-content:space-between;align-items:end;margin:17px 0 8px}
.section-title{font-size:1.13rem;font-weight:850;color:#173755}.section-sub{font-size:.78rem;color:#7b8d9e;margin-top:2px}
.badge{display:inline-block;padding:4px 8px;border-radius:999px;font-size:.68rem;font-weight:800}
.badge-long{background:#eaf8f1;color:#16885b}.badge-cash{background:#edf2f7;color:#64788c}
.footer-note{font-size:.72rem;color:#8997a6;text-align:center;margin-top:20px}

@media(max-width:1100px){
 .kpi-grid{grid-template-columns:repeat(3,1fr)} .mid-grid{grid-template-columns:1fr}
 .hero-status{grid-template-columns:1fr}
}
@media(max-width:700px){
 .kpi-grid{grid-template-columns:repeat(2,1fr)} .hero-title{font-size:2rem}
 .hero{padding:20px 18px}.quick-grid{grid-template-columns:1fr}.stats-strip{grid-template-columns:1fr 1fr}
}
</style>""",unsafe_allow_html=True)

st.caption("Trading companion • signalen • bevestigen • Auto Paper • voorbereid op Auto Live")
st.caption("Laatste koers en open P/L gebruiken de recentste beschikbare 1H-prijs; trendlogica blijft 1D/4H/1H.")
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


def latest_live_prices(state):
    prices = {}
    for asset in state.get("positions", {}):
        try:
            meta = CFG["portfolio"]["assets"][asset]
            d = fetch(meta["ticker"], "1h")
            if not d.empty:
                prices[asset] = float(d["close"].iloc[-1])
        except Exception:
            pass
    return prices


st.markdown("""
<div class="hero">
  <div class="brand">
    <div class="brand-icon"><i></i><i></i><i></i></div>
    <div>
      <div class="hero-title">AI Trend Trader</div>
      <div class="hero-sub">Slimmer traden. Rustiger leven.</div>
      <div class="hero-desc">AI-gedreven trendstrategieën op meerdere markten. Paper trading mode.</div>
    </div>
  </div>
  <div class="hero-status">
    <div class="status-card"><div class="status-icon status-green">🛡️</div><div><div class="status-title">PAPER ONLY</div><div class="status-sub">Live handelen uitgeschakeld</div></div></div>
    <div class="status-card"><div class="status-icon status-blue">💾</div><div><div class="status-title">Persistente opslag actief</div><div class="status-sub">via Supabase</div></div></div>
    <div class="status-card"><div class="status-icon status-blue">✈️</div><div><div class="status-title">Telegram-meldingen actief</div><div class="status-sub">Real-time updates</div></div></div>
  </div>
</div>
""", unsafe_allow_html=True)

tabs=st.tabs(["Dashboard","Automatisering","Instrumenten","Forward test","Performance","Live scanner","Events","Tradehistoriek","Meldingen"])


with tabs[0]:
    if st.button("▶️ Update paper portfolio nu",type="primary"):
        with st.spinner("Markten scannen en paper portfolio bijwerken..."):
            state,mode=run_once()
        st.success("Paper portfolio bijgewerkt.")

    state,_=load_state()
    auto=normalize_automation(state)
    positions=state.get("positions",{})
    hist=state.get("equity_history",[])
    with st.spinner("Actuele portefeuillewaarden ophalen..."):
        live_prices=latest_live_prices(state)
    marks=marked_portfolio_values(state, live_prices)
    stats=trade_stats(state)
    dd=max_drawdown_pct(state)
    total_pl=marks["equity"]-float(state.get("starting_equity",5000.0))

    def money(v): return f"€{v:,.2f}"
    def klass(v): return "positive" if v>0 else ("negative" if v<0 else "")

    cards=[
        ("💼","Equity",money(marks["equity"]),f"{marks['total_return_pct']:+.2f}%","red" if marks["total_return_pct"]<0 else ""),
        ("💶","Paper cash",money(marks["cash"]),"Beschikbaar",""),
        ("📈","Open P/L",money(marks["open_pnl"]),f"{marks['open_pnl']:+.2f}","red" if marks["open_pnl"]<0 else ""),
        ("🏆","Gerealiseerd P/L",money(marks["realized_pnl"]),"Gesloten trades",""),
        ("🥧","Waarde open posities",money(marks["market_value"]),"Mark-to-market",""),
        ("📊","Totale P/L sinds start",money(total_pl),f"{marks['total_return_pct']:+.2f}%","red" if total_pl<0 else ""),
        ("📋","Open posities",str(len(positions)),"Actief",""),
        ("✅","Gesloten trades",str(stats["count"]),"Historiek",""),
        ("🎯","Winrate",f"{stats['winrate']:.1f}%","Resultaat",""),
        ("🛡️","Max drawdown",f"{dd:.2f}%","Risico","")
    ]
    html='<div class="kpi-grid">'
    for icon,label,value,foot,sp in cards:
        valclass=klass(total_pl if label=="Totale P/L sinds start" else (marks["open_pnl"] if label=="Open P/L" else (marks["total_return_pct"] if label=="Equity" else 0)))
        html += f'<div class="kpi"><div class="kpi-top"><div class="kpi-ico">{icon}</div><div class="kpi-label">{label}</div></div><div class="kpi-value {valclass}">{value}</div><div class="kpi-foot {valclass}">{foot}</div><div class="spark {sp}"></div></div>'
    html+='</div>'
    st.markdown(html,unsafe_allow_html=True)

    st.markdown('<div class="mid-grid"><div class="panel"><div class="panel-title">Portfolio prestatie</div><div class="panel-sub">Ontwikkeling van je equity (paper trading)</div>',unsafe_allow_html=True)
    if hist:
        h=pd.DataFrame(hist)
        h["time"]=pd.to_datetime(h["time"])
        h=h.set_index("time")
        st.line_chart(h["equity"],height=320)
    stat_html=f'''<div class="stats-strip">
      <div class="statx"><div class="statx-l">Start waarde</div><div class="statx-v">€{float(state.get("starting_equity",5000.0)):,.2f}</div></div>
      <div class="statx"><div class="statx-l">Huidige waarde</div><div class="statx-v">€{marks["equity"]:,.2f}</div></div>
      <div class="statx"><div class="statx-l">Totaal rendement</div><div class="statx-v {"negative" if marks["total_return_pct"]<0 else "positive"}">{marks["total_return_pct"]:+.2f}%</div></div>
      <div class="statx"><div class="statx-l">Open P/L</div><div class="statx-v">€{marks["open_pnl"]:,.2f}</div></div>
      <div class="statx"><div class="statx-l">Cash</div><div class="statx-v">€{marks["cash"]:,.2f}</div></div>
    </div></div>'''
    st.markdown(stat_html,unsafe_allow_html=True)

    st.markdown('''<div class="panel">
      <div class="panel-title">Snelle acties</div><div class="panel-sub">Beheer je trading setup en automatiseer je strategieën.</div>
      <div class="quick-grid">
        <div class="quick"><div class="quick-ico">⚙️</div><div><div class="quick-title">Automatisering</div><div class="quick-sub">Configureer en start je strategieën</div></div></div>
        <div class="quick"><div class="quick-ico">▶️</div><div><div class="quick-title">Live trading</div><div class="quick-sub">Voorbereid voor latere koppeling</div></div></div>
        <div class="quick"><div class="quick-ico">📊</div><div><div class="quick-title">Performance</div><div class="quick-sub">Analyseer resultaten en statistieken</div></div></div>
        <div class="quick"><div class="quick-ico">📄</div><div><div class="quick-title">Tradehistoriek</div><div class="quick-sub">Bekijk gesloten trades en posities</div></div></div>
      </div>
      <div class="tip">💡 <b>Tip</b><br>Je handelt momenteel in paper mode. De app volgt automatisch je strategie en risicobeperkingen.</div>
    </div></div>''',unsafe_allow_html=True)

    enabled_assets=state.setdefault("enabled_assets",{})
    for asset in CFG["portfolio"]["assets"]: enabled_assets.setdefault(asset,True)
    rows=[]
    for asset in CFG["portfolio"]["assets"]:
        pos=positions.get(asset)
        if pos:
            last_price=live_prices.get(asset,pos.get("last_price",pos["entry"]))
            qty=float(pos.get("qty",0))
            pnl=(last_price-pos["entry"])*qty
            pct=((last_price-pos["entry"])/pos["entry"])*100
            dist=((last_price-pos.get("trail_stop",0))/last_price)*100 if last_price else 0
            rows.append({"Markt":asset,"Nieuwe trades":"AAN" if enabled_assets.get(asset,True) else "UIT","Status":"LONG","Entry":round(pos["entry"],2),"Laatste koers":round(last_price,2),"Trailing stop":round(pos.get("trail_stop",0),2),"Afstand tot stop %":round(dist,2),"Open P/L €":round(pnl,2),"Open P/L %":round(pct,2)})
        else:
            rows.append({"Markt":asset,"Nieuwe trades":"AAN" if enabled_assets.get(asset,True) else "UIT","Status":"CASH","Entry":None,"Laatste koers":None,"Trailing stop":None,"Afstand tot stop %":None,"Open P/L €":0,"Open P/L %":0})

    st.markdown('<div class="section-head"><div><div class="section-title">Actieve posities</div><div class="section-sub">Overzicht van je huidige posities en real-time inzichten.</div></div></div>',unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    st.markdown('<div class="footer-note">AI Trend Trader • Multi-asset trend trading • Aangedreven door AI</div>',unsafe_allow_html=True)
with tabs[1]:
    state,_=load_state()
    auto=normalize_automation(state)
    status=broker_status(state)

    st.subheader("Automatisering & Risk Guard")
    st.caption("Vul het beschikbare kapitaal in. De app stelt conservatieve waarden voor. De gebruiker kan aanpassen, maar nooit boven de harde veiligheidsgrenzen.")

    account_capital=st.number_input(
        "Beschikbaar kapitaal (€)",
        min_value=100.0,
        value=float(auto.get("account_capital",5000.0)),
        step=100.0
    )
    suggestion=suggested_settings(account_capital)

    if st.button("🛡️ Gebruik veilig voorstel"):
        auto.update(suggestion)
        auto["account_capital"]=float(account_capital)
        state["automation"]=auto
        save_state(state, update_last_run=False)
        st.success("Veilig voorstel toegepast. Herlaad of wijzig hieronder verder binnen de toegestane grenzen.")

    mode_labels=list(MODES.values())
    reverse_modes={v:k for k,v in MODES.items()}
    current_label=MODES.get(auto.get("mode","auto_paper"),"Auto Paper")
    selected_label=st.selectbox("Execution mode",mode_labels,index=mode_labels.index(current_label))
    selected_mode=reverse_modes[selected_label]

    c1,c2=st.columns(2)
    max_positions=c1.number_input(
        "Max. open posities",
        min_value=1,
        max_value=HARD_LIMITS["max_open_positions_max"],
        value=int(auto.get("max_open_positions",suggestion["max_open_positions"])),
        step=1
    )
    risk_pct=c2.number_input(
        "Risico per trade (%)",
        min_value=0.1,
        max_value=HARD_LIMITS["risk_per_trade_pct_max"],
        value=float(auto.get("risk_per_trade_pct",suggestion["risk_per_trade_pct"])),
        step=0.05
    )

    c1,c2=st.columns(2)
    daily_loss=c1.number_input(
        "Max. dagverlies (%)",
        min_value=0.5,
        max_value=HARD_LIMITS["daily_loss_pct_max"],
        value=float(auto.get("max_daily_loss_pct",suggestion["max_daily_loss_pct"])),
        step=0.25
    )
    heat=c2.number_input(
        "Max. totaal portefeuillerisico (%)",
        min_value=0.5,
        max_value=HARD_LIMITS["portfolio_heat_pct_max"],
        value=float(auto.get("max_portfolio_heat_pct",suggestion["max_portfolio_heat_pct"])),
        step=0.25
    )

    c1,c2=st.columns(2)
    reserve=c1.number_input(
        "Min. cashreserve (%)",
        min_value=HARD_LIMITS["min_cash_reserve_pct"],
        max_value=50.0,
        value=float(auto.get("min_cash_reserve_pct",suggestion["min_cash_reserve_pct"])),
        step=2.5
    )
    require_stop=c2.checkbox("Stop verplicht",value=bool(auto.get("require_stop",True)))

    emergency=st.toggle(
        "🛑 Noodstop — blokkeer alle nieuwe automatische entries",
        value=bool(auto.get("emergency_stop",False))
    )

    st.info(
        f"Voorstel bij €{account_capital:,.0f}: "
        f"{suggestion['risk_per_trade_pct']:.2f}% risico/trade • "
        f"{suggestion['max_open_positions']} posities • "
        f"{suggestion['max_portfolio_heat_pct']:.2f}% totaal risico • "
        f"{suggestion['min_cash_reserve_pct']:.1f}% cashreserve."
    )

    if selected_mode=="auto_live":
        st.warning("Auto Live blijft vergrendeld totdat een broker/exchange veilig gekoppeld en getest is.")
    elif selected_mode=="auto_paper":
        st.success("Auto Paper: automatische paper entries/exits, begrensd door Risk Guard.")

    if st.button("💾 Automatisering opslaan", type="primary"):
        auto["mode"]=selected_mode
        auto["account_capital"]=float(account_capital)
        auto["max_open_positions"]=int(max_positions)
        auto["risk_per_trade_pct"]=float(risk_pct)
        auto["max_daily_loss_pct"]=float(daily_loss)
        auto["max_portfolio_heat_pct"]=float(heat)
        auto["min_cash_reserve_pct"]=float(reserve)
        auto["require_stop"]=bool(require_stop)
        auto["emergency_stop"]=bool(emergency)
        auto["live_enabled"]=False
        auto=clamp_settings(auto)
        state["automation"]=auto
        save_state(state, update_last_run=False)
        st.success("Instellingen opgeslagen binnen de harde veiligheidsgrenzen.")

    st.markdown("#### Huidige bescherming")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Open posities",len(state.get("positions",{})))
    c2.metric("Portfolio heat",f"{portfolio_heat_pct(state):.2f}%")
    c3.metric("Cash",f"€{state.get('cash',0):,.2f}")
    c4.metric("Noodstop","AAN" if auto.get("emergency_stop") else "UIT")

    st.caption(
        "Nieuwe entries worden automatisch geweigerd bij te weinig vrije cash, te veel open posities, "
        "te hoog totaal risico of actieve noodstop."
    )

with tabs[2]:
    state,_=load_state()
    enabled_assets=state.setdefault("enabled_assets", {})
    all_assets=list(CFG["portfolio"]["assets"].keys())
    for asset in all_assets:
        enabled_assets.setdefault(asset, True)

    st.subheader("Instrumenten voor nieuwe trades")
    st.caption("Uitgeschakeld = geen nieuwe positie openen. Een bestaande open positie blijft wel automatisch beheerd tot de normale exit.")

    current=[a for a in all_assets if enabled_assets.get(a,True)]
    selected=st.multiselect(
        "Welke instrumenten mogen nieuwe paper trades openen?",
        options=all_assets,
        default=current
    )

    if st.button("💾 Instrumentkeuze opslaan", type="primary"):
        for asset in all_assets:
            enabled_assets[asset] = asset in selected
        state["enabled_assets"] = enabled_assets
        save_state(state, update_last_run=False)
        st.success("Instrumentkeuze opgeslagen in Supabase.")

    rows=[]
    positions=state.get("positions",{})
    for asset in all_assets:
        enabled=enabled_assets.get(asset,True)
        open_pos=asset in positions
        if enabled:
            status="ACTIEF"
        elif open_pos:
            status="UIT VOOR NIEUWE TRADES — bestaande positie wordt beheerd"
        else:
            status="UIT"
        rows.append({
            "Instrument":asset,
            "Nieuwe trades":"JA" if enabled else "NEE",
            "Open positie":"JA" if open_pos else "NEE",
            "Status":status
        })
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)


with tabs[3]:
    state,_=load_state()
    st.subheader("Forward-test monitor")
    st.caption("Deze monitor beoordeelt alleen de paper-resultaten die vanaf nu werkelijk binnenkomen. De strategie wordt hier niet automatisch aangepast.")

    assets=list(CFG["portfolio"]["assets"].keys())
    ft=forward_test_table(state, assets)
    rows=[]
    for r in ft:
        pf = r["profit_factor"]
        pf_text = "∞" if pf == float("inf") else f"{pf:.2f}"
        milestone = f"{r['next_milestone']} trades" if r["next_milestone"] else "100+ trades"
        rows.append({
            "Markt": r["asset"],
            "Status": r["status"],
            "Gesloten trades": r["trades"],
            "Winrate %": round(r["winrate"],1),
            "Profit factor": pf_text,
            "Gem. trade €": round(r["avg_trade"],2),
            "Volgende meetpunt": milestone
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("#### Meetpunten")
    st.write("**20 trades** = eerste bruikbare indruk • **50 trades** = sterkere steekproef • **100 trades** = veel betrouwbaarder beeld.")
    st.info("Een positieve status is geen garantie op toekomstige winst. We gebruiken deze pagina vooral om te vermijden dat we de strategie te snel aanpassen op enkele trades.")

    w=weekly_summary(state)
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Portfolio rendement",f"{w['return_pct']:+.2f}%")
    c2.metric("Max drawdown",f"{w['max_dd']:.2f}%")
    c3.metric("Gesloten trades",w["trades"])
    c4.metric("Winrate",f"{w['winrate']:.1f}%")

    c1,c2,c3=st.columns(3)
    pf=w["profit_factor"]
    c1.metric("Profit factor","∞" if pf==float("inf") else f"{pf:.2f}")
    c2.metric("Open P/L",f"€{w['open_pnl']:.2f}")
    c3.metric("Gerealiseerd P/L",f"€{w['realized_pnl']:.2f}")

with tabs[4]:
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

with tabs[5]:
    if st.button("🔎 Scan 1D / 4H / 1H",type="primary"):
        out=[]
        assets=list(CFG["portfolio"]["assets"].keys())
        bar=st.progress(0)
        for i,asset in enumerate(assets,1):
            snap=market_snapshot(asset)
            detail=action_details(asset,snap)
            state_now,_=load_state()
            enabled_now=state_now.setdefault("enabled_assets", {}).get(asset, True)
            out.append({
                "Markt":asset,
                "Trading":"AAN" if enabled_now else "UIT",
                "1D":snap["1d"]["trend"],
                "4H":snap["4h"]["trend"],
                "1H":snap["1h"]["trend"],
                "Actie":detail["action"],
                "1D uitleg":detail["detail_1d"],
                "4H uitleg":detail["detail_4h"],
                "1H uitleg":detail["detail_1h"]
            })
            bar.progress(i/len(assets))
        st.session_state["scan"]=pd.DataFrame(out)
    if "scan" in st.session_state:
        st.dataframe(st.session_state["scan"],use_container_width=True,hide_index=True)
        st.caption("Je ziet altijd eerst BULLISH / BEARISH / NEUTRAAL. ‘Trading UIT’ betekent dat de scanner wel analyseert, maar geen nieuwe positie opent.")

with tabs[6]:
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

with tabs[7]:
    state,_=load_state()
    trades=state.get("trades",[])
    if not trades:
        st.info("Nog geen gesloten paper trades.")
    else:
        t=pd.DataFrame(trades)
        st.dataframe(t,use_container_width=True,hide_index=True)

with tabs[8]:
    st.write("Automatische meldingen gaan naar Telegram bij PAPER LONG, trailing-stop update en PAPER EXIT.")
    st.write("v0.9 kan daarnaast elke avond één dagelijkse portfolio-samenvatting sturen.")
    if telegram_ready or discord_ready:
        if st.button("🔔 Stuur testmelding"):
            ok,target=notify("✅ AI Trend Trader v1.2.3 testmelding — notificaties werken.")
            if ok:
                st.success(f"Testmelding verstuurd via {target}.")
            else:
                st.error(f"Melding kon niet worden verstuurd: {target}")
    else:
        st.warning("Nog geen notificatie-secrets ingesteld.")
