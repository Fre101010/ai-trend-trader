from __future__ import annotations

def realized_pnl(p):
    return sum(float(t.get("pnl",0)) for t in p.get("trades",[]))

def current_equity(p):
    eq=float(p.get("cash",0))
    for pos in p.get("positions",{}).values():
        eq += float(pos.get("qty",0))*float(pos.get("last_price",pos.get("entry",0)))
    return eq

def open_pnl(p):
    total=0.0
    for pos in p.get("positions",{}).values():
        entry=float(pos.get("entry",0)); last=float(pos.get("last_price",entry)); qty=float(pos.get("qty",0))
        total += (last-entry)*qty
    return total

def marked_values(p, live_prices=None):
    live_prices=live_prices or {}
    cash=float(p.get("cash",0)); market=0.0; opnl=0.0
    for asset,pos in p.get("positions",{}).items():
        entry=float(pos.get("entry",0)); qty=float(pos.get("qty",0))
        px=float(live_prices.get(asset,pos.get("last_price",entry)))
        market += qty*px; opnl += (px-entry)*qty
    eq=cash+market
    return {"cash":cash,"market_value":market,"equity":eq,"open_pnl":opnl,"realized_pnl":realized_pnl(p)}

def trade_stats(p):
    pnls=[float(t.get("pnl",0)) for t in p.get("trades",[])]
    wins=[x for x in pnls if x>0]; losses=[x for x in pnls if x<0]
    gp=sum(wins); gl=abs(sum(losses))
    pf=(gp/gl) if gl>0 else (float("inf") if gp>0 else 0.0)
    return {
        "count":len(pnls),
        "wins":len(wins),
        "losses":len(losses),
        "winrate":len(wins)/len(pnls)*100 if pnls else 0.0,
        "profit_factor":pf,
        "avg_trade":sum(pnls)/len(pnls) if pnls else 0.0
    }

def max_drawdown_pct(p):
    vals=[float(x.get("equity",0)) for x in p.get("equity_history",[]) if x.get("equity") is not None]
    if not vals:return 0.0
    peak=vals[0]; dd=0.0
    for v in vals:
        peak=max(peak,v)
        if peak>0: dd=min(dd,(v-peak)/peak*100)
    return dd

def total_state_equity(state):
    return sum(current_equity(p) for p in state.get("portfolios",{}).values())
