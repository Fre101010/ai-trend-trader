from datetime import datetime,timezone
from trading_core import CFG,market_snapshot,desired_action,size_for_risk
from storage import load_state,save_state
def run_once():
 state,mode=load_state();fee=CFG['execution']['fee_rate'];slip=CFG['execution']['slippage'];posmap=state.setdefault('positions',{});trades=state.setdefault('trades',[]);total=state.get('cash',5000.0)
 for asset,meta in CFG['portfolio']['assets'].items():
  snap=market_snapshot(asset);price=snap['1d']['price'];action=desired_action(asset,snap);p=CFG['profiles'][meta['profile']];pos=posmap.get(asset)
  if pos:
   pos['trail_stop']=max(pos['trail_stop'],price-p['trail_atr']*snap['1d']['atr']);pos['last_price']=price;pos['unrealized_pnl']=(price-pos['entry'])*pos['qty'];trend_exit=not(snap['1d']['trend']=='BULLISH' and snap['4h']['trend']=='BULLISH');stop_hit=price<=pos['trail_stop']
   if trend_exit or stop_hit:
    exit_px=price*(1-slip);gross=pos['qty']*exit_px;exit_fee=gross*fee;pnl=(exit_px-pos['entry'])*pos['qty']-exit_fee-pos.get('entry_fee',0);state['cash']+=gross-exit_fee;trades.append({'asset':asset,'entry_time':pos['entry_time'],'exit_time':datetime.now(timezone.utc).isoformat(),'entry':pos['entry'],'exit':exit_px,'qty':pos['qty'],'pnl':pnl,'reason':'trend_exit' if trend_exit else 'trailing_stop'});del posmap[asset];pos=None
   else: total+=pos['qty']*price
  if pos is None and action=='LONG':
   allocation=state['cash']*meta['allocation_weight'];stop=price-p['initial_stop_atr']*snap['1d']['atr'];qty=size_for_risk(allocation,price,stop);entry=price*(1+slip);notional=qty*entry;entry_fee=notional*fee
   if qty>0 and notional+entry_fee<=state['cash']:
    state['cash']-=notional+entry_fee;posmap[asset]={'entry_time':datetime.now(timezone.utc).isoformat(),'entry':entry,'qty':qty,'initial_stop':stop,'trail_stop':stop,'entry_fee':entry_fee,'last_price':price,'unrealized_pnl':0.0};total+=qty*price
 state['equity_history'].append({'time':datetime.now(timezone.utc).isoformat(),'equity':round(total,2)});mode=save_state(state);return state,mode
if __name__=='__main__':
 s,m=run_once();print('paper run complete',m,s['cash'],list(s['positions']))
