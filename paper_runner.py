from datetime import datetime, timezone
from trading_core import CFG, market_snapshot, desired_action, size_for_risk
from storage import load_state, save_state
from notifier import notify
from analytics import current_equity
from risk_guard import clamp_settings

def add_event(p, kind, asset, message, extra=None, do_notify=True):
    event={"time":datetime.now(timezone.utc).isoformat(),"kind":kind,"asset":asset,"message":message,"extra":extra or {}}
    p.setdefault("events",[]).append(event)
    p["events"]=p["events"][-500:]
    if do_notify: notify(message)

def run_portfolio(p, portfolio_id):
    mode = "swing" if portfolio_id=="swing" else "active"
    fee=CFG["execution"]["fee_rate"]; slip=CFG["execution"]["slippage"]
    positions=p.setdefault("positions",{}); trades=p.setdefault("trades",[])
    enabled=p.setdefault("enabled_assets",{})
    auto=clamp_settings(p.setdefault("automation",{}))

    for asset,meta in CFG["portfolio"]["assets"].items():
        enabled.setdefault(asset,True)
        snap=market_snapshot(asset,mode)
        action=desired_action(asset,snap,mode)
        price=snap["1h"]["price"] if mode=="swing" else snap["15m"]["price"]
        prof=CFG["profiles"][meta["profile"]]
        pos=positions.get(asset)

        if pos:
            atr_src=snap["1d"]["atr"] if mode=="swing" else snap["1h"]["atr"]
            trail_mult=prof["trail_atr"] if mode=="swing" else 2.0
            new_trail=max(float(pos["trail_stop"]), price-trail_mult*atr_src)
            pos["trail_stop"]=new_trail; pos["last_price"]=price
            pos["unrealized_pnl"]=(price-pos["entry"])*pos["qty"]

            if mode=="swing":
                trend_exit=not (snap["1d"]["trend"]=="BULLISH" and snap["4h"]["trend"]=="BULLISH")
            else:
                trend_exit=not (snap["4h"]["trend"]=="BULLISH" and snap["1h"]["trend"]=="BULLISH")
            stop_hit=price<=new_trail

            if trend_exit or stop_hit:
                exit_px=price*(1-slip); gross=pos["qty"]*exit_px; exit_fee=gross*fee
                pnl=(exit_px-pos["entry"])*pos["qty"]-exit_fee-pos.get("entry_fee",0)
                p["cash"] += gross-exit_fee
                reason="trend_exit" if trend_exit else "trailing_stop"
                trade={"asset":asset,"portfolio":portfolio_id,"strategy_mode":mode,"entry_time":pos["entry_time"],
                       "exit_time":datetime.now(timezone.utc).isoformat(),"entry":pos["entry"],"exit":exit_px,
                       "qty":pos["qty"],"pnl":pnl,"reason":reason}
                trades.append(trade)
                add_event(p,"EXIT",asset,f"🛑 PAPER EXIT — {portfolio_id.upper()} — {asset}\nResultaat: €{pnl:.2f}",trade,True)
                del positions[asset]
                pos=None

        if pos is None and enabled.get(asset,True) and action=="LONG" and auto.get("mode","auto_paper")=="auto_paper":
            if auto.get("emergency_stop"): continue
            if len(positions)>=int(auto.get("max_open_positions",5)): continue
            allocation=float(p.get("cash",0))*float(meta.get("allocation_weight",0.2))
            atr_src=snap["1d"]["atr"] if mode=="swing" else snap["1h"]["atr"]
            stop_mult=prof["initial_stop_atr"] if mode=="swing" else 1.6
            stop=price-stop_mult*atr_src
            qty=size_for_risk(allocation,price,stop,meta.get("risk_multiplier",1.0),auto.get("risk_per_trade_pct",0.5))
            entry=price*(1+slip); notional=qty*entry; entry_fee=notional*fee
            reserve=current_equity(p)*float(auto.get("min_cash_reserve_pct",12.5))/100.0
            if qty>0 and notional+entry_fee <= max(0,float(p.get("cash",0))-reserve):
                p["cash"] -= notional+entry_fee
                positions[asset]={"entry_time":datetime.now(timezone.utc).isoformat(),"portfolio":portfolio_id,
                                  "strategy_mode":mode,"entry":entry,"qty":qty,"initial_stop":stop,
                                  "trail_stop":stop,"entry_fee":entry_fee,"last_price":price,"unrealized_pnl":0.0}
                add_event(p,"ENTRY",asset,f"🟢 PAPER LONG OPEN — {portfolio_id.upper()} — {asset}\nEntry: {entry:.2f}\nStop: {stop:.2f}",{},True)

    p.setdefault("equity_history",[]).append({"time":datetime.now(timezone.utc).isoformat(),"equity":round(current_equity(p),2)})
    p["equity_history"]=p["equity_history"][-2000:]

def run_once():
    state,mode=load_state()
    for pid in ["swing","active"]:
        run_portfolio(state["portfolios"][pid],pid)
    mode=save_state(state)
    return state,mode

if __name__=="__main__":
    s,m=run_once()
    print("paper run complete",m)
