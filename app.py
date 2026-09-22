import pandas as pd
import altair as alt
import streamlit as st
from trading_core import CFG, fetch, market_snapshot, desired_action
from storage import load_state, save_state, StorageUnavailable
from paper_runner import run_once, close_position
from clean_reset import clean_reset
from analytics import marked_values, trade_stats, max_drawdown_pct, portfolio_integrity

st.set_page_config(page_title="AI Trend Trader v2.5.1", page_icon="📈", layout="wide")

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


/* v2.4.2 premium pill navigation */
div[data-testid="stTabs"] {
  margin-top:.35rem;
}

/* Horizontal scroll container */
div[data-testid="stTabs"] > div:first-child {
  overflow-x:auto !important;
  overflow-y:hidden !important;
  scrollbar-width:none !important;
  -webkit-overflow-scrolling:touch;
  padding:.25rem .05rem .55rem .05rem;
}
div[data-testid="stTabs"] > div:first-child::-webkit-scrollbar{
  display:none !important;
}

div[data-testid="stTabs"] [role="tablist"]{
  display:flex !important;
  flex-wrap:nowrap !important;
  gap:.55rem !important;
  min-width:max-content !important;
  border-bottom:0 !important;
  padding:.15rem .05rem !important;
}

/* Pills */
div[data-testid="stTabs"] button[role="tab"]{
  display:inline-flex !important;
  align-items:center !important;
  justify-content:center !important;
  min-height:44px !important;
  padding:.62rem .95rem !important;
  border-radius:999px !important;
  border:1px solid #dce8f3 !important;
  background:#ffffff !important;
  color:#35516d !important;
  font-weight:800 !important;
  font-size:.9rem !important;
  white-space:nowrap !important;
  box-shadow:0 4px 14px rgba(27,61,96,.06) !important;
  transition:all .18s ease !important;
  opacity:1 !important;
}

/* Active pill */
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{
  background:linear-gradient(135deg,#2f80ed,#1d6fd5) !important;
  color:#ffffff !important;
  border-color:#2f80ed !important;
  box-shadow:0 7px 18px rgba(47,128,237,.24) !important;
  transform:translateY(-1px);
}

/* Text inside pills */
div[data-testid="stTabs"] button[role="tab"] p,
div[data-testid="stTabs"] button[role="tab"] span{
  color:inherit !important;
  font-weight:inherit !important;
  opacity:1 !important;
  margin:0 !important;
}

/* Kill Streamlit's default underline */
div[data-testid="stTabs"] [data-baseweb="tab-highlight"]{
  display:none !important;
}
div[data-testid="stTabs"] [data-baseweb="tab-border"]{
  display:none !important;
}

/* Hover only where supported */
@media (hover:hover){
  div[data-testid="stTabs"] button[role="tab"]:hover{
    border-color:#aacbec !important;
    background:#f5f9fe !important;
    color:#245f9d !important;
    transform:translateY(-1px);
  }
  div[data-testid="stTabs"] button[role="tab"][aria-selected="true"]:hover{
    background:linear-gradient(135deg,#2f80ed,#1d6fd5) !important;
    color:#fff !important;
  }
}

/* Mobile nav: comfortable finger-sized pills and subtle fade cue */
@media(max-width:650px){
  div[data-testid="stTabs"]{
    position:relative;
    margin-left:-.1rem;
    margin-right:-.1rem;
  }

  div[data-testid="stTabs"] > div:first-child{
    padding:.4rem .15rem .7rem .15rem !important;
  }

  div[data-testid="stTabs"] [role="tablist"]{
    gap:.5rem !important;
  }

  div[data-testid="stTabs"] button[role="tab"]{
    min-height:46px !important;
    padding:.64rem .9rem !important;
    font-size:.86rem !important;
    border-radius:15px !important;
  }
}

/* Nested open-position tabs slightly more compact, still readable. */
div[data-testid="stTabs"] div[data-testid="stTabs"] button[role="tab"]{
  min-height:40px !important;
  padding:.52rem .8rem !important;
  font-size:.82rem !important;
  background:#f8fbfe !important;
}
div[data-testid="stTabs"] div[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{
  background:linear-gradient(135deg,#ef5963,#d94650) !important;
  color:#fff !important;
  border-color:#ef5963 !important;
  box-shadow:0 6px 16px rgba(239,89,99,.2) !important;
}


/* v2.4.3 — hard mobile viewport lock */
html,
body,
#root,
[data-testid="stAppViewContainer"],
.stApp {
  width:100% !important;
  max-width:100% !important;
  overflow-x:hidden !important;
  overscroll-behavior-x:none !important;
}

*,
*::before,
*::after { box-sizing:border-box; }

[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
.block-container {
  width:100% !important;
  max-width:100% !important;
  min-width:0 !important;
  overflow-x:hidden !important;
}

.hero,
.status-grid,
.kpi-grid,
.portfolio-grid,
.portfolio-card,
.kpi,
.section-head,
[data-testid="stDataFrame"],
[data-testid="stVegaLiteChart"],
[data-testid="stVegaLiteChart"] > div,
iframe {
  max-width:100% !important;
  min-width:0 !important;
}

[data-testid="stVegaLiteChart"] {
  width:100% !important;
  overflow:hidden !important;
  touch-action:pan-y !important;
  overscroll-behavior-x:none !important;
}

div[data-testid="stTabs"] {
  width:100% !important;
  max-width:100% !important;
  min-width:0 !important;
  overflow:hidden !important;
}

div[data-testid="stTabs"] > div:first-child {
  width:100% !important;
  max-width:100% !important;
  overflow-x:auto !important;
  overflow-y:hidden !important;
  overscroll-behavior-x:contain !important;
  touch-action:pan-x !important;
  -webkit-overflow-scrolling:touch;
}

div[data-testid="stTabs"] [role="tabpanel"] {
  width:100% !important;
  max-width:100% !important;
  min-width:0 !important;
  overflow-x:hidden !important;
}

[data-testid="stDataFrame"] {
  width:100% !important;
  overflow-x:auto !important;
  overscroll-behavior-x:contain !important;
}

@media(max-width:650px){
  .block-container{
    width:100% !important;
    max-width:100vw !important;
    padding-left:.75rem !important;
    padding-right:.75rem !important;
    margin:0 !important;
  }

  .hero{
    width:100% !important;
    max-width:100% !important;
    margin-left:0 !important;
    margin-right:0 !important;
    padding:1rem !important;
  }

  .brand{
    width:100% !important;
    max-width:100% !important;
    min-width:0 !important;
  }

  .hero-title,
  .hero-sub,
  .hero-desc,
  .status-title,
  .status-sub{
    overflow-wrap:anywhere;
  }

  .status-grid{
    width:100% !important;
    grid-template-columns:1fr !important;
  }

  .kpi-grid{
    width:100% !important;
    grid-template-columns:repeat(2,minmax(0,1fr)) !important;
  }
}


/* v2.4.4 — mobile navigation + clipped content fix */

/* iOS Safari: keep the document anchored to the viewport. */
html, body {
  width:100% !important;
  max-width:100% !important;
  overflow-x:clip !important;
  overscroll-behavior-x:none !important;
  touch-action:pan-y !important;
}

.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
.block-container {
  width:100% !important;
  max-width:100% !important;
  min-width:0 !important;
  margin-left:0 !important;
  margin-right:0 !important;
  transform:none !important;
}

/* Do not horizontally scroll the menu anymore. All buttons wrap. */
div[data-testid="stTabs"] {
  width:100% !important;
  max-width:100% !important;
  overflow:visible !important;
}

div[data-testid="stTabs"] > div:first-child {
  width:100% !important;
  max-width:100% !important;
  overflow:visible !important;
  touch-action:pan-y !important;
  padding:.35rem 0 .65rem 0 !important;
}

div[data-testid="stTabs"] [role="tablist"] {
  display:flex !important;
  flex-wrap:wrap !important;
  width:100% !important;
  min-width:0 !important;
  gap:.45rem !important;
  padding:0 !important;
}

div[data-testid="stTabs"] button[role="tab"] {
  flex:0 0 auto !important;
  min-width:0 !important;
  max-width:100% !important;
}

/* Main content panels may never extend outside the viewport. */
div[data-testid="stTabs"] [role="tabpanel"],
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"],
[data-testid="column"],
[data-testid="stToggle"],
[data-testid="stButton"],
[data-testid="stMarkdownContainer"] {
  max-width:100% !important;
  min-width:0 !important;
}

/* Toggle labels stay inside the screen. */
[data-testid="stToggle"] label,
[data-testid="stToggle"] p,
[data-testid="stToggle"] span {
  white-space:normal !important;
  overflow-wrap:anywhere !important;
}

/* Buttons and controls should not push the page wider. */
[data-testid="stButton"] button,
[data-testid="stSelectbox"],
[data-testid="stNumberInput"],
[data-testid="stRadio"] {
  max-width:100% !important;
}

/* Charts: vertical page scrolling only, no plot dragging. */
[data-testid="stVegaLiteChart"] {
  width:100% !important;
  max-width:100% !important;
  overflow:hidden !important;
  touch-action:pan-y !important;
}

@media(max-width:650px){
  .block-container {
    width:100% !important;
    max-width:100% !important;
    padding-left:.8rem !important;
    padding-right:.8rem !important;
    overflow-x:clip !important;
  }

  .hero {
    width:100% !important;
    max-width:100% !important;
    margin:0 0 1rem 0 !important;
  }

  /* Main menu pills form a clean button grid instead of disappearing off-screen. */
  div[data-testid="stTabs"] [role="tablist"] {
    gap:.45rem !important;
  }

  div[data-testid="stTabs"] button[role="tab"] {
    flex:1 1 calc(50% - .45rem) !important;
    width:auto !important;
    min-height:44px !important;
    padding:.58rem .65rem !important;
    justify-content:center !important;
    text-align:center !important;
    border-radius:14px !important;
    font-size:.80rem !important;
  }

  /* Position tabs can be narrower; they also wrap safely. */
  div[data-testid="stTabs"] div[data-testid="stTabs"] button[role="tab"] {
    flex:0 1 auto !important;
    min-width:110px !important;
  }

  /* Instrument switches in a clean full-width vertical list. */
  [data-testid="stToggle"] {
    width:100% !important;
    padding:.18rem 0 !important;
  }

  [data-testid="stToggle"] label {
    width:100% !important;
    display:flex !important;
  }

  /* Prevent long headings from being clipped on the left/right. */
  h1,h2,h3,h4,
  .section-title,
  .section-sub,
  .portfolio-title,
  .portfolio-sub {
    max-width:100% !important;
    overflow-wrap:anywhere !important;
  }
}


/* v2.4.5 chart range selector */
[data-testid="stSegmentedControl"] {
  max-width:100% !important;
  margin:.15rem 0 .55rem 0 !important;
}
[data-testid="stSegmentedControl"] button {
  min-height:38px !important;
  border-radius:12px !important;
  font-size:.78rem !important;
  font-weight:750 !important;
}
@media(max-width:650px){
  [data-testid="stSegmentedControl"]{
    width:100% !important;
  }
}

</style>
""", unsafe_allow_html=True)

try:
    state, store_mode = load_state()
except StorageUnavailable as e:
    st.error(
        "⚠️ Opslag tijdelijk niet bereikbaar. Uit veiligheid wordt GEEN lege "
        "portefeuille getoond en worden geen trades uitgevoerd."
    )
    st.code(str(e))
    st.stop()

if str(store_mode).startswith("cache-readonly"):
    st.warning(
        "⚠️ Supabase is tijdelijk niet bereikbaar. Je ziet de laatst geldige "
        "lokale cache in alleen-lezen modus. Automatisch handelen is gepauzeerd "
        "tot Supabase opnieuw bereikbaar is."
    )

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

                range_options = {
                    "Kort": 60,
                    "Normaal": 100,
                    "Ruim": 140,
                }
                range_choice = st.segmented_control(
                    "Grafiekbereik",
                    options=list(range_options.keys()),
                    default="Normaal",
                    key=f"chart_range_{pid}_{asset}",
                    label_visibility="collapsed",
                )
                candle_count = range_options.get(range_choice or "Normaal", 100)
                df = fetch(ticker, tf).tail(candle_count).copy()

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

                # Extra lege ruimte rechts zodat de huidige koers niet tegen
                # de rand van de grafiek geplakt staat.
                x_start = chart_df["time"].min()
                x_last = chart_df["time"].max()
                x_span = x_last - x_start
                right_padding = x_span * 0.12 if x_span > pd.Timedelta(0) else pd.Timedelta(hours=1)
                x_end = x_last + right_padding

                base = alt.Chart(chart_df).encode(
                    x=alt.X(
                        "time:T",
                        title=None,
                        scale=alt.Scale(domain=[x_start, x_end])
                    )
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
                    x=alt.X("time:T", scale=alt.Scale(domain=[x_start, x_end])),
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
                    x=alt.X("time:T", scale=alt.Scale(domain=[x_start, x_end])),
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
                ).properties(height=340)

                st.altair_chart(chart, use_container_width=True)

                st.caption(
                    f"Afstand huidige koers tot trailing stop: {distance_stop:.2f}% • "
                    f"Timeframe: {tf_label} • Positie: {side} • "
                    f"Grafiekbereik: {range_choice or 'Normaal'}"
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




# One-time clean reset gate.
reset_ok = (
    str(state.get("repair_info",{}).get("version",""))=="2.5.0"
    and str(state.get("repair_info",{}).get("mode",""))=="clean_reset"
)

if not reset_ok:
    st.error(
        "⚠️ Eénmalige clean reset vereist. Automatische trading blijft geblokkeerd "
        "tot de corrupte paper-state volledig is vervangen."
    )
    st.info(
        "Deze reset start opnieuw vanaf een boekhoudkundig zuivere basis: "
        "Swing €3.998,70 + Active €1.000,00. De bevestigde historische Goud-trade "
        "van -€1,30 blijft bewaard. Oude open posities worden bewust niet meegenomen."
    )
    if st.button("🧹 Clean reset v2.5.0 uitvoeren", type="primary", key="clean_reset_v250"):
        try:
            clean_reset()
            st.success("Clean reset uitgevoerd. De app wordt opnieuw geladen.")
            st.rerun()
        except Exception as e:
            st.error(f"Reset mislukt: {type(e).__name__}: {e}")
    st.stop()

# Integrity status after clean reset.
live_by_portfolio = {
    "swing": live_prices_for(state["portfolios"]["swing"], "swing"),
    "active": live_prices_for(state["portfolios"]["active"], "active"),
}
integrity = portfolio_integrity(state, live_by_portfolio)
if not integrity["ok"]:
    st.error(
        f"⚠️ Integriteitscontrole wijkt af met €{integrity['delta']:.2f}. "
        "Automatische runner blijft geblokkeerd."
    )
else:
    st.success("✅ Portefeuille-integriteit OK.")

tabs = st.tabs([
    "🏠 Dashboard",
    "📈 Swing",
    "⚡ Active",
    "🔁 Transfer",
    "🎛 Instrumenten",
    "🔎 Scanner",
    "📚 Historiek",
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
        try:
            with st.spinner("Swing en Active analyseren..."):
                state, store_mode = run_once()
            if store_mode == "locked-skip":
                st.info(
                    "Er liep al een automatische tradingrun. Deze extra controle "
                    "is overgeslagen om dubbele trades/meldingen te voorkomen."
                )
            else:
                st.success("Beide portefeuilles zijn bijgewerkt.")
            st.rerun()
        except StorageUnavailable as e:
            st.error(
                "Bijwerken gestopt omdat de persistente opslag tijdelijk niet "
                "betrouwbaar bereikbaar is. Er is niets gereset."
            )
            st.code(str(e))

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
        for asset in CFG["portfolio"]["assets"]:
            enabled.setdefault(asset, True)
            enabled[asset] = st.toggle(
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
    '<div class="footer">AI Trend Trader v2.5.1 • Swing + Active • Paper-first multi-asset trend trading</div>',
    unsafe_allow_html=True,
)
