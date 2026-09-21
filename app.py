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

st.set_page_config(page_title="AI Trend Trader v1.3.2",page_icon="📈",layout="wide")
st.markdown("""<style>
:root{--nav:#0f2845;--nav2:#173c67;--blue:#2f80ed;--green:#19a76f;--red:#ee5661;--ink:#102a49;--line:#e3ebf3;}
.stApp{background:linear-gradient(180deg,#eef5fb 0,#f8fbff 220px,#fff 620px);color:var(--ink);}
.block-container{max-width:1420px;padding-top:.9rem;padding-bottom:4rem}
[data-testid="stHeader"]{background:linear-gradient(90deg,var(--nav),var(--nav2))}
div[data-testid="stTabs"] button{font-weight:700;color:#445f79;padding:.6rem .9rem}
div[data-testid="stTabs"] button[aria-selected="true"]{color:var(--blue);background:#edf5ff;border-radius:10px 10px 0 0;border-bottom:3px solid var(--blue)}
.stButton>button{border-radius:12px;min-height:46px;font-weight:750;border:1px solid #dce7f2}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,#3388ee,#1d6ed3);color:white;border:0}
[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:16px;overflow:hidden;box-shadow:0 5px 22px rgba(24,59,95,.06)}
.hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;background:linear-gradient(135deg,#fff,#eef6ff);border:1px solid #dde9f5;border-radius:22px;padding:22px 24px;box-shadow:0 10px 30px rgba(24,59,95,.08);margin-bottom:14px}
.hero-title{font-size:2.35rem;font-weight:850;line-height:1.05;color:#102a49}
.hero-sub{font-size:1rem;color:#667d94;margin-top:7px}
.status-wrap{display:flex;gap:9px;flex-wrap:wrap;margin-top:14px}
.status{border-radius:11px;padding:9px 11px;font-size:.82rem;font-weight:750;background:#fff;border:1px solid #dfe8f1;color:#35506d}
.status.good{background:#effaf5;color:#147d52;border-color:#d6efe2}
.status.info{background:#eef6ff;color:#2561a8;border-color:#d8e9ff}
.hero-side{text-align:right;font-size:.84rem;color:#72879c;line-height:1.55}
.section-head{margin:18px 0 10px}
.section-title{font-size:1.15rem;font-weight:800;color:#173654}
.section-sub{font-size:.88rem;color:#7a8a9a;margin-top:2px}
.kpi-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:13px;margin:12px 0 14px}
.kpi{background:white;border:1px solid var(--line);border-radius:18px;padding:15px;min-height:125px;box-shadow:0 7px 25px rgba(24,59,95,.07)}
.kpi.green{border-top:4px solid var(--green)} .kpi.red{border-top:4px solid var(--red)} .kpi.blue{border-top:4px solid var(--blue)}
.kpi-head{display:flex;align-items:center;gap:8px;color:#587087;font-size:.78rem;font-weight:750}
.kpi-icon{width:32px;height:32px;border-radius:10px;background:#edf5ff;display:flex;align-items:center;justify-content:center;font-size:17px}
.kpi-value{font-size:1.62rem;font-weight:850;color:var(--ink);margin-top:12px;line-height:1.05}
.kpi-note{font-size:.77rem;margin-top:8px;color:#7c8d9f}
.kpi.green .kpi-note{color:#168b5d}.kpi.red .kpi-note{color:#da4651}
.mini-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px;margin:0 0 17px}
.mini{display:flex;gap:11px;align-items:center;background:#fff;border:1px solid var(--line);border-radius:16px;padding:14px;box-shadow:0 5px 18px rgba(24,59,95,.05)}
.mini-icon{width:39px;height:39px;border-radius:11px;background:#f0f6fc;display:flex;align-items:center;justify-content:center;font-size:19px}
.mini-label{font-size:.75rem;color:#718497;font-weight:700}
.mini-value{font-size:1.28rem;font-weight:850;color:#102a49;margin-top:2px}
.meta-line{font-size:.78rem;color:#8392a2;margin:7px 0}
@media(max-width:1100px){.kpi-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:700px){.hero{flex-direction:column}.hero-side{text-align:left}.hero-title{font-size:1.9rem}.kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.mini-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.kpi-value{font-size:1.35rem}}
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
  <div>
    <div class="hero-title">📊 AI Trend Trader</div>
    <div class="hero-sub">Slimmer traden. Rustiger volgen. Multi-asset trend trading met automatische paper-uitvoering en risicobewaking.</div>
    <div class="status-wrap">
      <span class="status good">🛡️ PAPER ONLY</span>
      <span class="status good">💾 Supabase actief</span>
      <span class="status info">🔔 Telegram actief</span>
    </div>
  </div>
  <div class="hero-side">
    <b>AI Trend Trader v1.3.2</b><br>
    1D • 4H • 1H analyse<br>
    Risk Guard actief
  </div>
</div>
""", unsafe_allow_html=True)

tabs=st.tabs(["Dashboard","Automatisering","Instrumenten","Forward test","Performance","Live scanner","Events","Tradehistoriek","Meldingen"])


with tabs[0]:
    st.markdown('<div class="section-head"><div class="section-title">Dashboard</div><div class="section-sub">Actuele portefeuille, prestaties en open posities in één overzicht.</div></div>', unsafe_allow_html=True)

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
    total_pl=marks["equity"]-float(state.get("starting_equity",5000.0))
    dd=max_drawdown_pct(state)

    def money(v):
        return f"€{v:,.2f}"

    def tone(v):
        return "green" if v>0 else ("red" if v<0 else "blue")

    cards=[
        ("Equity",money(marks["equity"]),f"{marks['total_return_pct']:+.2f}% sinds start",tone(marks["total_return_pct"]),"📈"),
        ("Paper cash",money(marks["cash"]),"Beschikbaar saldo","blue","💶"),
        ("Open P/L",money(marks["open_pnl"]),"Niet gerealiseerd",tone(marks["open_pnl"]),"📊"),
        ("Gerealiseerde P/L",money(marks["realized_pnl"]),"Gesloten trades",tone(marks["realized_pnl"]),"🏆"),
        ("Waarde open posities",money(marks["market_value"]),"Mark-to-market","blue","💼"),
        ("Totale P/L sinds start",money(total_pl),f"{marks['total_return_pct']:+.2f}%",tone(total_pl),"🎯"),
    ]

    html='<div class="kpi-grid">'
    for title,value,note,t,icon in cards:
        html += (
            f'<div class="kpi {t}">'
            f'<div class="kpi-head"><span class="kpi-icon">{icon}</span>{title}</div>'
            f'<div class="kpi-value">{value}</div>'
            f'<div class="kpi-note">{note}</div>'
            f'</div>'
        )
    html+='</div>'
    st.markdown(html,unsafe_allow_html=True)

    minis=[
        ("Open posities",len(positions),"📚"),
        ("Gesloten trades",stats["count"],"✅"),
        ("Winrate",f"{stats['winrate']:.1f}%","🎯"),
        ("Max drawdown",f"{dd:.2f}%","🛡️"),
    ]
    html='<div class="mini-grid">'
    for label,value,icon in minis:
        html += (
            f'<div class="mini"><div class="mini-icon">{icon}</div>'
            f'<div><div class="mini-label">{label}</div><div class="mini-value">{value}</div></div></div>'
        )
    html+='</div>'
    st.markdown(html,unsafe_allow_html=True)

    meta = f'Execution mode: <b>{MODES.get(auto.get("mode","auto_paper"),auto.get("mode"))}</b>'
    if auto.get("emergency_stop"):
        meta += ' • 🛑 NOODSTOP ACTIEF'
    meta += f' &nbsp;•&nbsp; Laatste automatische run: {state.get("last_run") or "nog niet uitgevoerd"}'
    st.markdown(f'<div class="meta-line">{meta}</div>', unsafe_allow_html=True)

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
                "Markt":asset,"Nieuwe trades":"AAN" if trade_enabled else "UIT","Status":"LONG",
                "Entry":round(pos["entry"],2),"Laatste koers":round(last_price,2),
                "Trailing stop":round(pos.get("trail_stop",0),2),
                "Afstand tot stop %":round(stop_distance,2),
                "Open P/L €":round(open_pnl_eur,2),"Open P/L %":round(open_pct,2)
            })
        else:
            rows.append({
                "Markt":asset,"Nieuwe trades":"AAN" if trade_enabled else "UIT","Status":"CASH",
                "Entry":None,"Laatste koers":None,"Trailing stop":None,
                "Afstand tot stop %":None,"Open P/L €":0,"Open P/L %":0
            })

    st.markdown('<div class="section-head"><div class="section-title">Actieve posities</div><div class="section-sub">Realtime mark-to-market overzicht, trailing stops en resultaat per markt.</div></div>', unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

    if hist:
        st.markdown('<div class="section-head"><div class="section-title">Portfolio prestatie</div><div class="section-sub">Ontwikkeling van je paper equity doorheen de tijd.</div></div>', unsafe_allow_html=True)
        h=pd.DataFrame(hist)
        h["time"]=pd.to_datetime(h["time"])
        h=h.set_index("time")
        st.line_chart(h["equity"],height=320)

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
