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


def forward_test_status_for_market(state, asset):
    trades = [t for t in state.get("trades", []) if t.get("asset") == asset]
    pnls = [float(t.get("pnl", 0.0)) for t in trades]
    count = len(pnls)
    wins = sum(1 for x in pnls if x > 0)
    losses = sum(1 for x in pnls if x < 0)
    gross_profit = sum(x for x in pnls if x > 0)
    gross_loss = abs(sum(x for x in pnls if x < 0))
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
    avg = sum(pnls) / count if count else 0.0
    wr = wins / count * 100 if count else 0.0

    if count < 20:
        status = "ONVOLDOENDE DATA"
    elif count < 50:
        status = "EERSTE STEEKPROEF"
    elif pf >= 1.25 and avg > 0:
        status = "POSITIEVE FORWARD-TEST"
    elif pf >= 1.0 and avg >= 0:
        status = "GEMENGD"
    else:
        status = "NEGATIEVE FORWARD-TEST"

    return {
        "asset": asset,
        "trades": count,
        "wins": wins,
        "losses": losses,
        "winrate": wr,
        "profit_factor": pf,
        "avg_trade": avg,
        "status": status,
        "next_milestone": 20 if count < 20 else (50 if count < 50 else (100 if count < 100 else None))
    }

def forward_test_table(state, assets):
    return [forward_test_status_for_market(state, a) for a in assets]

def daily_returns_from_equity(state):
    hist = state.get("equity_history", [])
    if len(hist) < 2:
        return []
    # Collapse to last equity value per UTC date
    by_day = {}
    for row in hist:
        t = str(row.get("time",""))
        if not t:
            continue
        day = t[:10]
        by_day[day] = float(row.get("equity", 0.0))
    days = sorted(by_day)
    vals = [by_day[d] for d in days]
    rets = []
    for i in range(1, len(vals)):
        if vals[i-1] != 0:
            rets.append((vals[i] / vals[i-1]) - 1.0)
    return rets

def sharpe_like(state):
    rets = daily_returns_from_equity(state)
    if len(rets) < 5:
        return None
    mean = sum(rets)/len(rets)
    var = sum((x-mean)**2 for x in rets)/(len(rets)-1)
    sd = var**0.5
    if sd == 0:
        return None
    return mean/sd*(252**0.5)

def weekly_summary(state):
    stats = trade_stats(state)
    return {
        "equity": current_equity(state),
        "return_pct": return_since_start_pct(state),
        "open_pnl": open_pnl(state),
        "realized_pnl": realized_pnl(state),
        "max_dd": max_drawdown_pct(state),
        "winrate": stats["winrate"],
        "profit_factor": stats["profit_factor"],
        "trades": stats["count"],
        "sharpe_like": sharpe_like(state)
    }
