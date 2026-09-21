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

st.set_page_config(page_title="AI Trend Trader v1.2.3",page_icon="📈",layout="wide")
st.markdown("""<style>
.block-container{padding-top:1rem;padding-bottom:4rem;max-width:1180px}
.stButton>button{width:100%;min-height:48px;border-radius:14px;font-weight:700}
div[data-testid="stMetric"]{border:1px solid rgba(128,128,128,.25);border-radius:16px;padding:12px}
</style>""",unsafe_allow_html=True)

st.title("📈 AI Trend Trader v1.2.3")
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

tabs=st.tabs(["Dashboard","Automatisering","Instrumenten","Forward test","Performance","Live scanner","Events","Tradehistoriek","Meldingen"])

with tabs[0]:
    if st.button("▶️ Update paper portfolio nu",type="primary"):
        with st.spinner("Markten scannen en paper portfolio bijwerken..."):
            state,mode=run_once()
        st.success("Paper portfolio bijgewerkt.")

    state,_=load_state()
    auto=normalize_automation(state)
    st.caption(f"Execution mode: **{MODES.get(auto.get('mode','auto_paper'), auto.get('mode'))}**" + (" • 🛑 NOODSTOP ACTIEF" if auto.get("emergency_stop") else ""))
    positions=state.get("positions",{})
    trades=state.get("trades",[])
    hist=state.get("equity_history",[])

    with st.spinner("Actuele portefeuillewaarden ophalen..."):
        live_prices=latest_live_prices(state)
    marks=marked_portfolio_values(state, live_prices)

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Equity",f"€{marks['equity']:,.2f}",f"{marks['total_return_pct']:+.2f}%")
    c2.metric("Paper cash",f"€{marks['cash']:,.2f}")
    c3.metric("Open P/L",f"€{marks['open_pnl']:,.2f}")
    c4.metric("Gerealiseerd P/L",f"€{marks['realized_pnl']:,.2f}")

    c1,c2=st.columns(2)
    c1.metric("Waarde open posities",f"€{marks['market_value']:,.2f}")
    c2.metric("Totale P/L sinds start",f"€{marks['equity']-float(state.get('starting_equity',5000.0)):,.2f}")

    c1,c2,c3,c4=st.columns(4)
    stats=trade_stats(state)
    pf=stats["profit_factor"]
    pf_text="∞" if pf==float("inf") else f"{pf:.2f}"
    c1.metric("Open posities",len(positions))
    c2.metric("Gesloten trades",stats["count"])
    c3.metric("Winrate",f"{stats['winrate']:.1f}%")
    c4.metric("Max drawdown",f"{max_drawdown_pct(state):.2f}%")

    st.caption(f"Laatste run: {state.get('last_run') or 'nog niet uitgevoerd'}")
    st.caption("Dashboardwaarden worden bij elke herlaadbeurt opnieuw gewaardeerd met de recentste beschikbare 1H-koers.")

    enabled_assets=state.setdefault("enabled_assets", {})
    for asset in CFG["portfolio"]["assets"]:
        enabled_assets.setdefault(asset, True)

    rows=[]
    for asset in CFG["portfolio"]["assets"]:
        pos=positions.get(asset)
        trade_enabled=enabled_assets.get(asset,True)
        if pos:
            last_price=live_prices.get(asset,pos.get("last_price",pos["entry"]))
            qty=float(pos.get("qty",0))
            open_pnl_eur=(last_price-pos["entry"])*qty
            open_pct=((last_price-pos["entry"])/pos["entry"])*100
            stop_distance=((last_price-pos.get("trail_stop",0))/last_price)*100 if last_price else 0
            rows.append({
                "Markt":asset,"Nieuwe trades":"AAN" if trade_enabled else "UIT","Status":"LONG","Entry":round(pos["entry"],2),
                "Laatste koers":round(last_price,2),
                "Trailing stop":round(pos.get("trail_stop",0),2),
                "Afstand tot stop %":round(stop_distance,2),
                "Open P/L €":round(open_pnl_eur,2),
                "Open P/L %":round(open_pct,2)
            })
        else:
            rows.append({"Markt":asset,"Nieuwe trades":"AAN" if trade_enabled else "UIT","Status":"CASH","Entry":None,"Laatste koers":None,
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
