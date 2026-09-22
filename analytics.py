from __future__ import annotations

def realized_pnl(p):
    return sum(float(t.get("pnl",0)) for t in p.get("trades",[]))

def current_equity(p):
    cash=float(p.get("cash",0))
    eq=cash
    for pos in p.get("positions",{}).values():
        qty=float(pos.get("qty",0))
        entry=float(pos.get("entry",0))
        last=float(pos.get("last_price",entry))
        side=pos.get("side","LONG")
        if side=="SHORT":
            margin=float(pos.get("margin_reserved",entry*qty))
            eq += margin + (entry-last)*qty
        else:
            eq += qty*last
    return eq

def open_pnl(p):
    total=0.0
    for pos in p.get("positions",{}).values():
        entry=float(pos.get("entry",0))
        last=float(pos.get("last_price",entry))
        qty=float(pos.get("qty",0))
        side=pos.get("side","LONG")
        if side=="SHORT":
            total += (entry-last)*qty
        else:
            total += (last-entry)*qty
    return total

def marked_values(p, live_prices=None):
    live_prices=live_prices or {}
    cash=float(p.get("cash",0))
    market=0.0
    opnl=0.0
    margin_value=0.0

    for asset,pos in p.get("positions",{}).items():
        entry=float(pos.get("entry",0))
        qty=float(pos.get("qty",0))
        px=float(live_prices.get(asset,pos.get("last_price",entry)))
        side=pos.get("side","LONG")

        if side=="SHORT":
            pnl=(entry-px)*qty
            opnl += pnl
            margin_value += entry*qty
        else:
            pnl=(px-entry)*qty
            opnl += pnl
            market += qty*px

    # Longs are held as market value; shorts are represented as reserved margin + P/L.
    eq=cash+market+margin_value+opnl
    return {
        "cash":cash,
        "market_value":market+margin_value,
        "equity":eq,
        "open_pnl":opnl,
        "realized_pnl":realized_pnl(p)
    }

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


def expected_total_capital(state):
    ledger=state.get("capital_ledger",{})
    initial=float(ledger.get("initial_total_capital",5000.0))
    deposits=float(ledger.get("external_deposits",0.0))
    withdrawals=float(ledger.get("external_withdrawals",0.0))
    return initial+deposits-withdrawals

def portfolio_integrity(state, live_prices_by_portfolio=None):
    live_prices_by_portfolio=live_prices_by_portfolio or {}
    total=0.0
    for pid,p in state.get("portfolios",{}).items():
        total += marked_values(p,live_prices_by_portfolio.get(pid,{}))["equity"]

    expected=expected_total_capital(state)
    # Realized/unrealized P/L legitimately changes equity, so compare against
    # expected capital + total realized/open P/L to detect phantom capital.
    total_open=0.0
    total_realized=0.0
    for pid,p in state.get("portfolios",{}).items():
        vals=marked_values(p,live_prices_by_portfolio.get(pid,{}))
        total_open += vals["open_pnl"]
        total_realized += vals["realized_pnl"]

    theoretical=expected+total_open+total_realized
    delta=total-theoretical
    ok=abs(delta) < 2.0
    return {
        "ok":ok,
        "actual_equity":total,
        "expected_equity":theoretical,
        "delta":delta,
        "base_capital":expected,
        "open_pnl":total_open,
        "realized_pnl":total_realized,
    }
