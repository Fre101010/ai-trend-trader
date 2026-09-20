import pandas as pd, streamlit as st
from trading_core import CFG,market_snapshot,desired_action
from storage import load_state
from paper_runner import run_once
st.set_page_config(page_title='AI Trend Trader v0.7',page_icon='📈',layout='centered')
st.markdown('<style>.block-container{padding-top:1rem;padding-bottom:4rem;max-width:950px}.stButton>button{width:100%;min-height:54px;border-radius:14px;font-weight:700}div[data-testid="stMetric"]{border:1px solid rgba(128,128,128,.25);border-radius:16px;padding:12px}</style>',unsafe_allow_html=True)
st.title('📈 AI Trend Trader v0.7');st.caption('Persistente paper trading • Goud • Nasdaq 100 ETF • S&P 500 ETF');st.success('🔒 PAPER ONLY — geen echte orders of brokerkoppeling.')
state,mode=load_state()
if mode=="supabase":
    st.success("💾 Persistente opslag actief via Supabase")
elif str(mode).startswith("supabase-error"):
    st.error("💾 Supabase is gevonden, maar de verbinding geeft nog een fout. Controleer Streamlit Secrets en Supabase Data API.")
else:
    st.warning("💾 Demo-opslag actief. Koppel Supabase voor echte persistentie.")
t1,t2,t3,t4=st.tabs(['Paper dashboard','Live scanner','Tradehistoriek','Instellingen'])
with t1:
 if st.button('▶️ Update paper portfolio nu',type='primary'):
  with st.spinner('Markten scannen en paper portfolio bijwerken...'): state,mode=run_once()
  st.success('Paper portfolio bijgewerkt.')
 state,_=load_state();positions=state.get('positions',{});trades=state.get('trades',[]);hist=state.get('equity_history',[]);equity=state.get('cash',0)+sum(p.get('qty',0)*p.get('last_price',p.get('entry',0)) for p in positions.values())
 a,b=st.columns(2);a.metric('Paper cash',f"€{state.get('cash',0):,.2f}");b.metric('Geschatte equity',f'€{equity:,.2f}')
 a,b=st.columns(2);a.metric('Open posities',len(positions));b.metric('Gesloten paper trades',len(trades));st.caption(f"Laatste run: {state.get('last_run') or 'nog niet uitgevoerd'}")
 rows=[]
 for asset in CFG['portfolio']['assets']:
  p=positions.get(asset);rows.append({'Markt':asset,'Status':'LONG' if p else 'CASH','Entry':round(p['entry'],2) if p else None,'Laatste koers':round(p.get('last_price',0),2) if p else None,'Trailing stop':round(p.get('trail_stop',0),2) if p else None,'Open P/L €':round(p.get('unrealized_pnl',0),2) if p else 0})
 st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
 if hist:
  h=pd.DataFrame(hist);h['time']=pd.to_datetime(h['time']);st.line_chart(h.set_index('time')['equity'])
with t2:
 if st.button('🔎 Scan 1D / 4H / 1H',type='primary'):
  out=[];assets=list(CFG['portfolio']['assets']);bar=st.progress(0)
  for i,a in enumerate(assets,1):
   s=market_snapshot(a);out.append({'Markt':a,'1D':s['1d']['trend'],'4H':s['4h']['trend'],'1H':s['1h']['trend'],'ADX 1D':round(s['1d']['adx'],1),'Actie':desired_action(a,s)});bar.progress(i/len(assets))
  st.session_state['scan']=pd.DataFrame(out)
 if 'scan' in st.session_state:st.dataframe(st.session_state['scan'],use_container_width=True,hide_index=True)
with t3:
 state,_=load_state();tr=state.get('trades',[])
 if not tr:st.info('Nog geen gesloten paper trades.')
 else:
  d=pd.DataFrame(tr);st.dataframe(d,use_container_width=True,hide_index=True);st.metric('Totaal gerealiseerde paper P/L',f"€{d['pnl'].sum():,.2f}");st.metric('Winrate',f"{(d['pnl']>0).mean()*100:.1f}%")
with t4:
 st.write('Kernportfolio: Goud, Nasdaq 100 ETF en S&P 500 ETF.');st.write('1D bepaalt de hoofdtrend, 4H bevestigt, 1H verfijnt. Alleen long in deze eerste paperfase.');st.write('Risico per trade: 0,5% van toegewezen paperkapitaal.');st.write('Opslagmodus:',mode);st.info('Voor automatische updates zonder de app te openen gebruik je de GitHub Actions workflow + Supabase.')
