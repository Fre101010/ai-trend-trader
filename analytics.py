from __future__ import annotations
from math import sqrt

def current_equity(state):
    equity = float(state.get("cash", 0.0))
    for pos in state.get("positions", {}).values():
        px = float(pos.get("last_price", pos.get("entry", 0.0)))
        equity += float(pos.get("qty", 0.0)) * px
    return equity

def realized_pnl(state):
    return sum(float(t.get("pnl", 0.0)) for t in state.get("trades", []))

def open_pnl(state):
    total = 0.0
    for p in state.get("positions", {}).values():
        entry = float(p.get("entry", 0.0))
        last = float(p.get("last_price", entry))
        qty = float(p.get("qty", 0.0))
        total += (last - entry) * qty
    return total

def trade_stats(state):
    trades = state.get("trades", [])
    pnls = [float(t.get("pnl", 0.0)) for t in trades]
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
    return {
        "count": len(pnls),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": (len(wins) / len(pnls) * 100.0) if pnls else 0.0,
        "profit_factor": pf,
        "avg_trade": (sum(pnls) / len(pnls)) if pnls else 0.0,
        "best_trade": max(pnls) if pnls else 0.0,
        "worst_trade": min(pnls) if pnls else 0.0,
    }

def max_drawdown_pct(state):
    hist = state.get("equity_history", [])
    vals = [float(x.get("equity", 0.0)) for x in hist if x.get("equity") is not None]
    if not vals:
        return 0.0
    peak = vals[0]
    max_dd = 0.0
    for v in vals:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (v - peak) / peak * 100.0
            if dd < max_dd:
                max_dd = dd
    return max_dd

def return_since_start_pct(state):
    start = float(state.get("starting_equity", 5000.0) or 5000.0)
    eq = current_equity(state)
    return ((eq / start) - 1.0) * 100.0 if start else 0.0

def per_market_stats(state):
    markets = {}
    for t in state.get("trades", []):
        a = t.get("asset", "Onbekend")
        m = markets.setdefault(a, {"trades":0,"pnl":0.0,"wins":0,"losses":0})
        pnl = float(t.get("pnl", 0.0))
        m["trades"] += 1
        m["pnl"] += pnl
        if pnl > 0: m["wins"] += 1
        if pnl < 0: m["losses"] += 1
    for a,m in markets.items():
        m["winrate"] = (m["wins"]/m["trades"]*100.0) if m["trades"] else 0.0
    return markets
