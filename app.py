import pandas as pd
import altair as alt
import streamlit as st
from trading_core import CFG, fetch, market_snapshot, desired_action
from storage import load_state, save_state
from paper_runner import run_once, close_position
from analytics import marked_values, trade_stats, max_drawdown_pct

st.set_page_config(page_title="AI Trend Trader v2.4.1.1", page_icon="📈", layout="wide")

st.markdown("""
<style>
:root{
  --nav:#0d2a4a;--nav2:#173f6c;--blue:#2f80ed;--blue2:#68a8f3;
  --ink:#102a49;--muted:#75889b;--line:#e3edf5;--green:#18a76f;--red:#ef5963;
}
.stApp{
  background:
    radial-gradient(circle at 82% 0%,rgba(68,139,218,.14),transparent 28%),
    linear-gradient(180deg,#edf5fc 0,#f8fbff 245px,#fff 760px);
  color:var(--ink);
}
.block-container{max-width:1540px;padding:0.8rem 1.25rem 4rem}
[data-testid="stHeader"]{background:linear-gradient(90deg,var(--nav),var(--nav2))}
div[data-testid="stTabs"] button{font-weight:750;color:#48637e;padding:.65rem .95rem}
div[data-testid="stTabs"] button[aria-selected="true"]{
  color:var(--blue);background:#eef6ff;border-radius:10px 10px 0 0;
  border-bottom:3px solid var(--blue);
}
.stButton>button{border-radius:12px;min-height:45px;font-weight:750;border:1px solid #dce8f3}
.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,#3388ef,#1d6fd5);color:#fff;border:0;
}
[data-testid="stDataFrame"]{
  border:1px solid var(--line);border-radius:16px;overflow:hidden;
  box-shadow:0 6px 24px rgba(25,60,95,.06);
}
.hero{
  position:relative;overflow:hidden;
  background:linear-gradient(135deg,#fff,#edf6ff);
  border:1px solid #dfe9f3;border-radius:22px;padding:24px 26px;
  box-shadow:0 10px 30px rgba(25,60,95,.08);margin-bottom:14px;
}
.hero:after{
  content:"";position:absolute;right:-75px;top:-105px;width:430px;height:300px;
  background:linear-gradient(135deg,rgba(87,151,225,.17),rgba(255,255,255,0));
  transform:rotate(-12deg);border-radius:50%;
}
.brand{display:flex;align-items:center;gap:14px;position:relative;z-index:2}
.brand-icon{
  width:54px;height:54px;border-radius:16px;background:linear-gradient(135deg,#2f80ed,#65a8f7);
  color:#fff;display:flex;align-items:flex-end;justify-content:center;gap:3px;padding:10px;
  box-shadow:0 8px 24px rgba(47,128,237,.23)
}
.brand-icon i{display:block;width:6px;background:#fff;border-radius:4px}
.brand-icon i:nth-child(1){height:15px}
.brand-icon i:nth-child(2){height:24px}
.brand-icon i:nth-child(3){height:33px}
.hero-title{font-size:2.45rem;font-weight:900;letter-spacing:-.04em;line-height:1;color:#102a49}
.hero-sub{font-size:1.12rem;color:#55718e;margin-top:6px}
.hero-desc{font-size:.88rem;color:#76899c;margin-top:5px}
.status-grid{
  display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:10px;
  margin-top:18px;max-width:920px;position:relative;z-index:2;
}
.status{
  background:rgba(255,255,255,.92);border:1px solid #dfeaf4;border-radius:14px;
  padding:11px 12px;box-shadow:0 6px 20px rgba(30,65,100,.06);
  display:flex;gap:10px;align-items:center
}
.status-ico{
  width:34px;height:34px;border-radius:10px;background:#edf5ff;
  display:flex;align-items:center;justify-content:center;font-size:18px
}
.status-title{font-size:.75rem;font-weight:850;color:#25435f}
.status-sub{font-size:.65rem;color:#8393a2;margin-top:2px}
.section-head{margin:18px 0 9px}
.section-title{font-size:1.18rem;font-weight:850;color:#173755}
.section-sub{font-size:.8rem;color:#7b8e9f;margin-top:2px}
.kpi-grid{
  display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:12px 0 15px;
}
.kpi{
  background:#fff;border:1px solid var(--line);border-radius:17px;padding:15px 16px;
  box-shadow:0 7px 24px rgba(30,65,100,.06);min-height:116px;
}
.kpi-top{display:flex;align-items:center;gap:9px}
.kpi-ico{
  width:34px;height:34px;border-radius:10px;background:#edf5ff;
  display:flex;align-items:center;justify-content:center;font-size:17px
}
.kpi-label{font-size:.77rem;font-weight:750;color:#59718a}
.kpi-value{font-size:1.62rem;font-weight:900;color:#102a49;margin-top:12px}
.kpi-sub{font-size:.71rem;color:#8493a2;margin-top:6px}
.neg{color:#df4651!important}
.pos{color:#168d60!important}
.portfolio-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
.portfolio-card{
  background:#fff;border:1px solid var(--line);border-radius:18px;padding:17px;
  box-shadow:0 7px 24px rgba(30,65,100,.06)
}
.portfolio-badge{
  display:inline-block;padding:5px 9px;border-radius:999px;background:#eef6ff;
  color:#2b67aa;font-size:.68rem;font-weight:850;margin-bottom:8px
}
.portfolio-title{font-size:1.18rem;font-weight:850;color:#173755}
.portfolio-sub{font-size:.77rem;color:#7c8f9f;margin-top:3px}
.portfolio-numbers{display:grid;grid-template-columns:repeat(2,1fr);gap:9px;margin-top:14px}
.pnum{background:#f8fbfe;border:1px solid #edf2f7;border-radius:13px;padding:11px}
.pnum-l{font-size:.68rem;color:#7e8e9d}
.pnum-v{font-size:1.18rem;font-weight:850;color:#183a5a;margin-top:3px}
.info-box{
  padding:12px 13px;border-radius:13px;background:#eef6ff;color:#2a5f96;
  font-size:.76rem;margin:10px 0 12px
}
.footer{font-size:.72rem;color:#8998a7;text-align:center;margin-top:22px}
@media(max-width:1050px){
  .status-grid{grid-template-columns:repeat(2,1fr)}
  .kpi-grid{grid-template-columns:repeat(2,1fr)}
  .portfolio-grid{grid-template-columns:1fr}
}
@media(max-width:650px){
  .hero-title{font-size:2rem}
  .status-grid{grid-template-columns:1fr}
  .kpi-grid{grid-template-columns:repeat(2,1fr)}
}

/* v2.4.1 mobile/readability fix: force native Streamlit widgets to stay dark
   on our light custom background, independent of iOS/system theme. */
.stApp,
.stApp p,
.stApp span,
.stApp label,
.stApp div {
  text-rendering: optimizeLegibility;
}

[data-testid="stMetric"],
[data-testid="stMetric"] * {
  color:#102a49 !important;
}

[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] *,
[data-testid="stMetricValue"],
[data-testid="stMetricValue"] *,
[data-testid="stMetricDelta"],
[data-testid="stMetricDelta"] * {
  opacity:1 !important;
}

[data-testid="stMetricLabel"] {
  color:#6f8194 !important;
}

[data-testid="stMetricValue"] {
  color:#102a49 !important;
}

[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] *,
.stCaption,
.stCaption * {
  color:#6f8194 !important;
  opacity:1 !important;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
  color:#173755;
}

[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4 {
  color:#102a49 !important;
}

/* Main and nested tabs: readable and horizontally scrollable on mobile. */
div[data-testid="stTabs"] > div:first-child {
  overflow-x:auto !important;
  overflow-y:hidden !important;
  scrollbar-width:none;
  -webkit-overflow-scrolling:touch;
}

div[data-testid="stTabs"] > div:first-child::-webkit-scrollbar {
  display:none;
}

div[data-testid="stTabs"] [role="tablist"] {
  flex-wrap:nowrap !important;
  min-width:max-content;
  gap:.15rem;
}

div[data-testid="stTabs"] button[role="tab"] {
  color:#415b75 !important;
  background:transparent !important;
  white-space:nowrap !important;
  opacity:1 !important;
}

div[data-testid="stTabs"] button[role="tab"] p,
div[data-testid="stTabs"] button[role="tab"] span {
  color:inherit !important;
  opacity:1 !important;
}

div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
  color:#ef5963 !important;
  background:#fff7f8 !important;
  border-bottom:3px solid #ef5963 !important;
}

/* Native controls inside position management. */
[data-testid="stButton"] button,
[data-testid="stButton"] button * {
  opacity:1 !important;
}

[data-testid="stAlert"] *,
[data-testid="stNotification"] * {
  opacity:1 !important;
}

/* iPhone/mobile: reduce oversized gaps and keep chart/metrics compact. */
@media(max-width:650px){
  .block-container{
    padding-left:.75rem !important;
    padding-right:.75rem !important;
  }

  [data-testid="stMetric"]{
    background:#fff !important;
    border:1px solid #e3edf5 !important;
    border-radius:14px !important;
    padding:.75rem !important;
  }

  [data-testid="stMetricValue"]{
    font-size:1.45rem !important;
  }

  [data-testid="stMetricLabel"]{
    font-size:.78rem !important;
  }

  div[data-testid="stTabs"] button[role="tab"]{
    padding:.5rem .72rem !important;
    font-size:.88rem !important;
  }
}

</style>
""", unsafe_allow_html=True)

state, store_mode = load_state()

st.markdown("""
<div class="hero">
  <div class="brand">
    <div class="brand-icon"><i></i><i></i><i></i></div>
    <div>
      <div class="hero-title">AI Trend Trader</div>
      <div class="hero-sub">Slimmer traden. Rustiger leven.</div>
      <div class="hero-desc">Twee strategieportefeuilles. Eén totaaloverzicht. Volledig paper-first.</div>
    </div>
  </div>
  <div class="status-grid">
    <div class="status"><div class="status-ico">🛡️</div><div><div class="status-title">PAPER ONLY</div><div class="status-sub">Live handelen uitgeschakeld</div></div></div>
    <div class="status"><div class="status-ico">💾</div><div><div class="status-title">SUPABASE</div><div class="status-sub">Persistente opslag actief</div></div></div>
    <div class="status"><div class="status-ico">📈</div><div><div class="status-title">SWING</div><div class="status-sub">1D / 4H / 1H</div></div></div>
    <div class="status"><div class="status-ico">⚡</div><div><div class="status-title">ACTIVE</div><div class="status-sub">4H / 1H / 15m • scan elke 5 min</div></div></div>
  </div>
</div>
""", unsafe_allow_html=True)

def live_prices_for(p, strategy):
    prices = {}
    tf = "1h" if strategy == "swing" else "15m"
    for asset in p.get("positions", {}):
        try:
            prices[asset] = float(fetch(CFG["portfolio"]["assets"][asset]["ticker"], tf)["close"].iloc[-1])
        except Exception:
            pass
    return prices

def get_marks(pid):
    p = state["portfolios"][pid]
    return marked_values(p, live_prices_for(p, pid))

def render_kpis(items):
    html = '<div class="kpi-grid">'
    for icon, label, value, sub, cls in items:
        html += (
            f'<div class="kpi">'
            f'<div class="kpi-top"><div class="kpi-ico">{icon}</div><div class="kpi-label">{label}</div></div>'
            f'<div class="kpi-value {cls}">{value}</div>'
            f'<div class="kpi-sub {cls}">{sub}</div>'
            f'</div>'
        )
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

def render_portfolio_summary(pid, title, subtitle):
    p = state["portfolios"][pid]
    marks = marked_values(p, live_prices_for(p, pid))
    open_cls = "neg" if marks["open_pnl"] < 0 else ("pos" if marks["open_pnl"] > 0 else "")
    html = (
        '<div class="portfolio-card">'
        f'<div class="portfolio-badge">{pid.upper()}</div>'
        f'<div class="portfolio-title">{title}</div>'
        f'<div class="portfolio-sub">{subtitle}</div>'
        '<div class="portfolio-numbers">'
        f'<div class="pnum"><div class="pnum-l">Equity</div><div class="pnum-v">€{marks["equity"]:,.2f}</div></div>'
        f'<div class="pnum"><div class="pnum-l">Vrije cash</div><div class="pnum-v">€{marks["cash"]:,.2f}</div></div>'
        f'<div class="pnum"><div class="pnum-l">Open P/L</div><div class="pnum-v {open_cls}">€{marks["open_pnl"]:,.2f}</div></div>'
        f'<div class="pnum"><div class="pnum-l">Open posities</div><div class="pnum-v">{len(p.get("positions", {}))}</div></div>'
        '</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)

def position_rows(pid):
    p = state["portfolios"][pid]
    prices = live_prices_for(p, pid)
    rows = []
    for asset in CFG["portfolio"]["assets"]:
        enabled = p.setdefault("enabled_assets", {}).get(asset, True)
        pos = p.get("positions", {}).get(asset)
        if pos:
            px = prices.get(asset, pos.get("last_price", pos["entry"]))
            qty = float(pos.get("qty", 0))
            side = pos.get("side", "LONG")

            if side == "SHORT":
                pnl = (pos["entry"] - px) * qty
                pct = ((pos["entry"] - px) / pos["entry"]) * 100 if pos["entry"] else 0
                dist = ((pos.get("trail_stop", 0) - px) / px) * 100 if px else 0
            else:
                pnl = (px - pos["entry"]) * qty
                pct = ((px - pos["entry"]) / pos["entry"]) * 100 if pos["entry"] else 0
                dist = ((px - pos.get("trail_stop", 0)) / px) * 100 if px else 0

            rows.append({
                "Markt": asset,
                "Nieuwe trades": "AAN" if enabled else "UIT",
                "Status": side,
                "Entry": round(pos["entry"], 2),
                "Laatste koers": round(px, 2),
                "Trailing stop": round(pos.get("trail_stop", 0), 2),
                "Afstand stop %": round(dist, 2),
                "Open P/L €": round(pnl, 2),
                "Open P/L %": round(pct, 2),
            })
        else:
            rows.append({
                "Markt": asset,
                "Nieuwe trades": "AAN" if enabled else "UIT",
                "Status": "CASH",
                "Entry": None,
                "Laatste koers": None,
                "Trailing stop": None,
                "Afstand stop %": None,
                "Open P/L €": 0.0,
                "Open P/L %": 0.0,
            })
    return rows



def render_position_charts(pid):
    p = state["portfolios"][pid]
    positions = p.get("positions", {})

    if not positions:
        st.info("Nog geen open posities in deze portefeuille.")
        return

    tf = "1h" if pid == "swing" else "15m"
    tf_label = "1 uur" if pid == "swing" else "15 minuten"

    st.markdown(
        '<div class="section-head"><div class="section-title">Open posities</div>'
        f'<div class="section-sub">Klik op een markt om de grafiek te bekijken. Timeframe: {tf_label}.</div></div>',
        unsafe_allow_html=True,
    )

    asset_names = list(positions.keys())
    asset_tabs = st.tabs(asset_names)

    for tab, asset in zip(asset_tabs, asset_names):
        with tab:
            pos = positions[asset]

            try:
                ticker = CFG["portfolio"]["assets"][asset]["ticker"]
                df = fetch(ticker, tf).tail(140).copy()

                if df.empty:
                    st.warning(f"Geen koersdata beschikbaar voor {asset}.")
                    continue

                chart_df = df.reset_index()
                time_col = chart_df.columns[0]
                chart_df = chart_df.rename(columns={time_col: "time"})
                chart_df["time"] = pd.to_datetime(chart_df["time"])

                current_price = float(chart_df["close"].iloc[-1])
                entry_price = float(pos["entry"])
                stop_price = float(pos.get("trail_stop", entry_price))
                qty = float(pos.get("qty", 0))

                side = pos.get("side", "LONG")
                if side == "SHORT":
                    open_pnl = (entry_price - current_price) * qty
                    open_pct = ((entry_price - current_price) / entry_price) * 100 if entry_price else 0.0
                    distance_stop = ((stop_price - current_price) / current_price) * 100 if current_price else 0.0
                else:
                    open_pnl = (current_price - entry_price) * qty
                    open_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price else 0.0
                    distance_stop = ((current_price - stop_price) / current_price) * 100 if current_price else 0.0

                initial_risk = float(pos.get("initial_risk", abs(entry_price-float(pos.get("initial_stop",stop_price)))))
                if side == "SHORT":
                    current_r = (entry_price-current_price)/initial_risk if initial_risk else 0.0
                else:
                    current_r = (current_price-entry_price)/initial_risk if initial_risk else 0.0
                max_r = max(float(pos.get("max_r_reached",current_r)), current_r)
                lock_stage = pos.get("profit_lock_stage","NONE")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Huidige koers", f"{current_price:,.2f}")
                c2.metric("Entry", f"{entry_price:,.2f}")
                c3.metric("Trailing stop", f"{stop_price:,.2f}")
                c4.metric(f"Open P/L ({side})", f"€{open_pnl:,.2f}", f"{open_pct:+.2f}%")

                r1, r2, r3 = st.columns(3)
                r1.metric("Huidige R", f"{current_r:.2f}R")
                r2.metric("Hoogste R", f"{max_r:.2f}R")
                stage_text = {
                    "NONE":"Normale trailing",
                    "1R_BREAK_EVEN":"Break-even beschermd",
                    "2R_TIGHT_TRAIL":"Winst-lock actief",
                }.get(lock_stage, lock_stage)
                r3.metric("Winstbescherming", stage_text)

                base = alt.Chart(chart_df).encode(
                    x=alt.X("time:T", title=None)
                )

                price_line = base.mark_line(
                    strokeWidth=2.5,
                    color="#2F80ED"
                ).encode(
                    y=alt.Y("close:Q", title="Koers", scale=alt.Scale(zero=False)),
                    tooltip=[
                        alt.Tooltip("time:T", title="Tijd"),
                        alt.Tooltip("close:Q", title="Koers", format=".2f"),
                    ],
                )

                entry_rule = alt.Chart(
                    pd.DataFrame({"y": [entry_price]})
                ).mark_rule(
                    color="#18A76F",
                    strokeDash=[8, 5],
                    strokeWidth=2,
                ).encode(y="y:Q")

                stop_rule = alt.Chart(
                    pd.DataFrame({"y": [stop_price]})
                ).mark_rule(
                    color="#EF5963",
                    strokeDash=[6, 5],
                    strokeWidth=2,
                ).encode(y="y:Q")

                last_row = pd.DataFrame({
                    "time": [chart_df["time"].iloc[-1]],
                    "close": [current_price],
                })

                current_point = alt.Chart(last_row).mark_point(
                    filled=True,
                    size=95,
                    color="#2F80ED",
                ).encode(
                    x="time:T",
                    y="close:Q"
                )

                labels = pd.DataFrame({
                    "label": [
                        f"ENTRY {entry_price:,.2f}",
                        f"TRAILING STOP {stop_price:,.2f}",
                    ],
                    "y": [entry_price, stop_price],
                    "time": [
                        chart_df["time"].iloc[-1],
                        chart_df["time"].iloc[-1]
                    ],
                })

                label_chart = alt.Chart(labels).mark_text(
                    align="right",
                    dx=-8,
                    dy=-7,
                    fontSize=11,
                    fontWeight="bold",
                ).encode(
                    x="time:T",
                    y="y:Q",
                    text="label:N",
                    color=alt.Color(
                        "label:N",
                        scale=alt.Scale(
                            domain=[
                                f"ENTRY {entry_price:,.2f}",
                                f"TRAILING STOP {stop_price:,.2f}"
                            ],
                            range=["#18A76F", "#EF5963"],
                        ),
                        legend=None,
                    ),
                )

                chart = (
                    price_line
                    + entry_rule
                    + stop_rule
                    + current_point
                    + label_chart
                ).properties(height=340).interactive()

                st.altair_chart(chart, use_container_width=True)

                st.caption(
                    f"Afstand huidige koers tot trailing stop: {distance_stop:.2f}% • "
                    f"Timeframe: {tf_label} • Positie: {side}"
                )

                st.markdown("#### Positie beheren")
                confirm_key=f"confirm_close_{pid}_{asset}"

                if not st.session_state.get(confirm_key,False):
                    if st.button(
                        f"💰 {asset} positie sluiten / winst nemen",
                        key=f"close_btn_{pid}_{asset}",
                    ):
                        st.session_state[confirm_key]=True
                        st.rerun()
                else:
                    st.warning(
                        f"Bevestig: {asset} {side} sluiten tegen de recentste beschikbare koers "
                        f"({current_price:,.2f})?"
                    )
                    b1,b2=st.columns(2)

                    if b1.button(
                        "✅ Ja, positie sluiten",
                        key=f"confirm_yes_{pid}_{asset}",
                        type="primary",
                    ):
                        fresh_state,_=load_state()
                        fresh_p=fresh_state["portfolios"][pid]
                        if asset not in fresh_p.get("positions",{}):
                            st.warning("Deze positie is intussen al gesloten.")
                        else:
                            trade=close_position(
                                fresh_p,
                                pid,
                                asset,
                                current_price,
                                reason="manual_close",
                                do_notify=True,
                            )
                            save_state(fresh_state,update_last_run=False)
                            st.session_state[confirm_key]=False
                            if trade:
                                st.success(
                                    f"{asset} gesloten. Gerealiseerd resultaat: €{trade['pnl']:.2f}"
                                )
                            st.rerun()

                    if b2.button(
                        "Annuleren",
                        key=f"confirm_no_{pid}_{asset}",
                    ):
                        st.session_state[confirm_key]=False
                        st.rerun()

            except Exception as e:
                st.warning(
                    f"Grafiek voor {asset} kon niet geladen worden: {type(e).__name__}"
                )

tabs = st.tabs([
    "Dashboard",
    "Swing Portfolio",
    "Active Portfolio",
    "Transfer",
    "Instrumenten",
    "Live scanner",
    "Historiek",
])

with tabs[0]:
    sw = get_marks("swing")
    ac = get_marks("active")
    total_eq = sw["equity"] + ac["equity"]
    total_cash = sw["cash"] + ac["cash"]
    total_open = sw["open_pnl"] + ac["open_pnl"]
    total_real = sw["realized_pnl"] + ac["realized_pnl"]

    st.markdown(
        '<div class="section-head"><div class="section-title">Totaal vermogen</div>'
        '<div class="section-sub">Gecombineerd overzicht van Swing + Active.</div></div>',
        unsafe_allow_html=True,
    )
    render_kpis([
        ("💼", "Totale equity", f"€{total_eq:,.2f}", "Swing + Active", ""),
        ("💶", "Totale cash", f"€{total_cash:,.2f}", "Vrij beschikbaar", ""),
        ("📊", "Totale open P/L", f"€{total_open:,.2f}", "Niet gerealiseerd", "neg" if total_open < 0 else ("pos" if total_open > 0 else "")),
        ("🏆", "Totale gerealiseerde P/L", f"€{total_real:,.2f}", "Gesloten trades", "neg" if total_real < 0 else ("pos" if total_real > 0 else "")),
    ])

    c1, c2 = st.columns(2)
    with c1:
        render_portfolio_summary("swing", "Swing Portfolio", "Rustigere trendtrades op 1D / 4H / 1H.")
    with c2:
        render_portfolio_summary("active", "Active Portfolio", "Kortere trendtrades op 4H / 1H / 15m.")

    st.markdown(
        '<div class="section-head"><div class="section-title">Snelle actie</div>'
        '<div class="section-sub">Werk beide paperportefeuilles bij met de nieuwste marktdata.</div></div>',
        unsafe_allow_html=True,
    )
    if st.button("▶️ Beide portefeuilles nu extra controleren", type="primary"):
        with st.spinner("Swing en Active analyseren..."):
            state, store_mode = run_once()
        st.success("Beide portefeuilles zijn bijgewerkt.")

with tabs[1]:
    p = state["portfolios"]["swing"]
    marks = marked_values(p, live_prices_for(p, "swing"))
    stats = trade_stats(p)
    dd = max_drawdown_pct(p)

    st.markdown(
        '<div class="section-head"><div class="section-title">Swing Portfolio</div>'
        '<div class="section-sub">1D / 4H / 1H — minder signalen, langere posities.</div></div>',
        unsafe_allow_html=True,
    )
    render_kpis([
        ("💼", "Equity", f"€{marks['equity']:,.2f}", "Swing", ""),
        ("💶", "Cash", f"€{marks['cash']:,.2f}", "Vrij beschikbaar", ""),
        ("📊", "Open P/L", f"€{marks['open_pnl']:,.2f}", "Niet gerealiseerd", "neg" if marks["open_pnl"] < 0 else ("pos" if marks["open_pnl"] > 0 else "")),
        ("🏆", "Gerealiseerd", f"€{marks['realized_pnl']:,.2f}", "Gesloten trades", ""),
        ("📋", "Open posities", str(len(p.get("positions", {}))), "Actief", ""),
        ("✅", "Gesloten trades", str(stats["count"]), "Historiek", ""),
        ("🎯", "Winrate", f"{stats['winrate']:.1f}%", "Forward test", ""),
        ("🛡️", "Max drawdown", f"{dd:.2f}%", "Risico", ""),
    ])
    st.dataframe(pd.DataFrame(position_rows("swing")), use_container_width=True, hide_index=True)
    render_position_charts("swing")

with tabs[2]:
    p = state["portfolios"]["active"]
    marks = marked_values(p, live_prices_for(p, "active"))
    stats = trade_stats(p)
    dd = max_drawdown_pct(p)

    st.markdown(
        '<div class="section-head"><div class="section-title">Active Portfolio</div>'
        '<div class="section-sub">4H / 1H / 15m — LONG + SHORT • break-even vanaf +1R • strakkere trailing vanaf +2R.</div></div>',
        unsafe_allow_html=True,
    )
    render_kpis([
        ("⚡", "Equity", f"€{marks['equity']:,.2f}", "Active", ""),
        ("💶", "Cash", f"€{marks['cash']:,.2f}", "Vrij beschikbaar", ""),
        ("📊", "Open P/L", f"€{marks['open_pnl']:,.2f}", "Niet gerealiseerd", "neg" if marks["open_pnl"] < 0 else ("pos" if marks["open_pnl"] > 0 else "")),
        ("🏆", "Gerealiseerd", f"€{marks['realized_pnl']:,.2f}", "Gesloten trades", ""),
        ("📋", "Open posities", str(len(p.get("positions", {}))), "Actief", ""),
        ("✅", "Gesloten trades", str(stats["count"]), "Historiek", ""),
        ("🎯", "Winrate", f"{stats['winrate']:.1f}%", "Forward test", ""),
        ("🛡️", "Max drawdown", f"{dd:.2f}%", "Risico", ""),
    ])
    st.dataframe(pd.DataFrame(position_rows("active")), use_container_width=True, hide_index=True)
    render_position_charts("active")

with tabs[3]:
    st.markdown(
        '<div class="section-head"><div class="section-title">Interne transfer</div>'
        '<div class="section-sub">Verplaats vrije cash tussen Swing en Active. Open posities blijven onaangeraakt.</div></div>',
        unsafe_allow_html=True,
    )

    sw_cash = float(state["portfolios"]["swing"].get("cash", 0))
    ac_cash = float(state["portfolios"]["active"].get("cash", 0))
    render_kpis([
        ("📈", "Swing cash", f"€{sw_cash:,.2f}", "Beschikbaar", ""),
        ("⚡", "Active cash", f"€{ac_cash:,.2f}", "Beschikbaar", ""),
        ("🔁", "Aantal transfers", str(len(state.get("transfers", []))), "Historiek", ""),
        ("🛡️", "Posities geraakt", "Nee", "Alleen vrije cash", ""),
    ])

    direction = st.selectbox("Van → Naar", ["Swing → Active", "Active → Swing"])
    source = "swing" if direction.startswith("Swing") else "active"
    target = "active" if source == "swing" else "swing"
    available = float(state["portfolios"][source].get("cash", 0))
    amount = st.number_input(
        "Bedrag (€)",
        min_value=0.0,
        max_value=max(0.0, available),
        value=0.0,
        step=50.0,
    )

    st.markdown(
        f'<div class="info-box">Vrije cash in <b>{source.title()}</b>: '
        f'€{available:,.2f}. Alleen dit vrije saldo kan worden overgezet.</div>',
        unsafe_allow_html=True,
    )

    if st.button("💸 Transfer uitvoeren", type="primary"):
        if amount <= 0:
            st.warning("Kies een bedrag groter dan €0.")
        elif amount > available:
            st.error("Onvoldoende vrije cash.")
        else:
            state["portfolios"][source]["cash"] -= amount
            state["portfolios"][target]["cash"] += amount
            state["transfers"].append({
                "time": pd.Timestamp.utcnow().isoformat(),
                "from": source,
                "to": target,
                "amount": amount,
            })
            save_state(state, update_last_run=False)
            st.success(f"€{amount:,.2f} overgezet van {source.title()} naar {target.title()}.")
            st.rerun()

    if state.get("transfers"):
        st.markdown(
            '<div class="section-head"><div class="section-title">Transferhistoriek</div></div>',
            unsafe_allow_html=True,
        )
        st.dataframe(pd.DataFrame(state["transfers"][-50:][::-1]), use_container_width=True, hide_index=True)

with tabs[4]:
    st.markdown(
        '<div class="section-head"><div class="section-title">Instrumenten per portefeuille</div>'
        '<div class="section-sub">Een markt kan in Swing, Active of in beide actief zijn.</div></div>',
        unsafe_allow_html=True,
    )

    for pid, label in [("swing", "Swing"), ("active", "Active")]:
        st.markdown(f"### {label}")
        p = state["portfolios"][pid]
        enabled = p.setdefault("enabled_assets", {})
        cols = st.columns(2)

        for i, asset in enumerate(CFG["portfolio"]["assets"]):
            enabled.setdefault(asset, True)
            enabled[asset] = cols[i % 2].toggle(
                asset,
                value=enabled[asset],
                key=f"{pid}_{asset}",
            )

        if st.button(f"💾 {label} instrumenten opslaan", key=f"save_{pid}"):
            p["enabled_assets"] = enabled
            save_state(state, update_last_run=False)
            st.success(f"{label} instrumenten opgeslagen.")

with tabs[5]:
    st.markdown(
        '<div class="section-head"><div class="section-title">Live scanner</div>'
        '<div class="section-sub">Vergelijk de trendvoorwaarden voor Swing of Active.</div></div>',
        unsafe_allow_html=True,
    )

    portfolio = st.radio("Scanner voor", ["Swing", "Active"], horizontal=True)
    mode_sel = portfolio.lower()

    if st.button("🔎 Scan markten", type="primary"):
        out = []
        with st.spinner(f"{portfolio}-markten analyseren..."):
            for asset in CFG["portfolio"]["assets"]:
                s = market_snapshot(asset, mode_sel)
                act = desired_action(asset, s, mode_sel)

                if mode_sel == "swing":
                    out.append({
                        "Markt": asset,
                        "1D": s["1d"]["trend"],
                        "4H": s["4h"]["trend"],
                        "1H": s["1h"]["trend"],
                        "Actie": act,
                    })
                else:
                    out.append({
                        "Markt": asset,
                        "4H": s["4h"]["trend"],
                        "1H": s["1h"]["trend"],
                        "15m": s["15m"]["trend"],
                        "Actie": act,
                    })

        st.session_state["scan_v21"] = pd.DataFrame(out)

    if "scan_v21" in st.session_state:
        st.dataframe(st.session_state["scan_v21"], use_container_width=True, hide_index=True)

with tabs[6]:
    st.markdown(
        '<div class="section-head"><div class="section-title">Tradehistoriek</div>'
        '<div class="section-sub">Bekijk Swing en Active afzonderlijk.</div></div>',
        unsafe_allow_html=True,
    )

    which = st.selectbox("Portfolio", ["Swing", "Active"])
    p = state["portfolios"][which.lower()]

    if p.get("trades"):
        st.dataframe(pd.DataFrame(p["trades"])[::-1], use_container_width=True, hide_index=True)
    else:
        st.info("Nog geen gesloten trades in deze portefeuille.")

st.markdown(
    '<div class="footer">AI Trend Trader v2.4.1 • Swing + Active • Paper-first multi-asset trend trading</div>',
    unsafe_allow_html=True,
)
