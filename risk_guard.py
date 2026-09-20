from __future__ import annotations

HARD_LIMITS = {
    "risk_per_trade_pct_max": 1.0,
    "daily_loss_pct_max": 3.0,
    "portfolio_heat_pct_max": 3.0,
    "max_open_positions_max": 8,
    "min_cash_reserve_pct": 10.0,
}

def suggested_settings(capital: float):
    capital = max(float(capital or 0), 0.0)

    # Conservative defaults; scale number of positions modestly with account size.
    if capital < 1000:
        max_pos = 2
        risk = 0.25
        heat = 0.75
        daily = 1.0
        reserve = 20.0
    elif capital < 5000:
        max_pos = 3
        risk = 0.35
        heat = 1.25
        daily = 1.5
        reserve = 15.0
    elif capital < 25000:
        max_pos = 5
        risk = 0.50
        heat = 2.0
        daily = 2.0
        reserve = 12.5
    else:
        max_pos = 6
        risk = 0.50
        heat = 2.5
        daily = 2.0
        reserve = 10.0

    return {
        "max_open_positions": max_pos,
        "risk_per_trade_pct": risk,
        "max_daily_loss_pct": daily,
        "max_portfolio_heat_pct": heat,
        "min_cash_reserve_pct": reserve,
    }

def clamp_settings(cfg: dict):
    cfg = dict(cfg or {})
    cfg["risk_per_trade_pct"] = min(max(float(cfg.get("risk_per_trade_pct",0.5)),0.1), HARD_LIMITS["risk_per_trade_pct_max"])
    cfg["max_daily_loss_pct"] = min(max(float(cfg.get("max_daily_loss_pct",2.0)),0.5), HARD_LIMITS["daily_loss_pct_max"])
    cfg["max_portfolio_heat_pct"] = min(max(float(cfg.get("max_portfolio_heat_pct",2.0)),0.5), HARD_LIMITS["portfolio_heat_pct_max"])
    cfg["max_open_positions"] = min(max(int(cfg.get("max_open_positions",5)),1), HARD_LIMITS["max_open_positions_max"])
    cfg["min_cash_reserve_pct"] = min(max(float(cfg.get("min_cash_reserve_pct",10.0)),HARD_LIMITS["min_cash_reserve_pct"]),50.0)
    return cfg

def position_risk_eur(pos: dict):
    entry = float(pos.get("entry",0))
    stop = float(pos.get("trail_stop", pos.get("initial_stop", entry)))
    qty = float(pos.get("qty",0))
    return max(0.0, (entry-stop)*qty)

def portfolio_heat_pct(state: dict):
    equity = float(state.get("cash",0))
    for p in state.get("positions",{}).values():
        equity += float(p.get("qty",0))*float(p.get("last_price",p.get("entry",0)))
    if equity <= 0:
        return 0.0
    total_risk = sum(position_risk_eur(p) for p in state.get("positions",{}).values())
    return total_risk/equity*100.0

def min_cash_required(state: dict, cfg: dict):
    equity = float(state.get("cash",0))
    for p in state.get("positions",{}).values():
        equity += float(p.get("qty",0))*float(p.get("last_price",p.get("entry",0)))
    return equity * float(cfg.get("min_cash_reserve_pct",10.0))/100.0

def guard_new_entry(state: dict, proposed_notional: float, proposed_risk_eur: float):
    auto = clamp_settings(state.get("automation",{}))
    cash = float(state.get("cash",0))
    open_positions = len(state.get("positions",{}))

    if auto.get("emergency_stop"):
        return False, "Noodstop actief"

    if open_positions >= auto["max_open_positions"]:
        return False, "Maximum aantal open posities bereikt"

    reserve = min_cash_required(state, auto)
    if cash - proposed_notional < reserve:
        return False, "Onvoldoende vrije cash na verplichte cashreserve"

    equity = cash + sum(
        float(p.get("qty",0))*float(p.get("last_price",p.get("entry",0)))
        for p in state.get("positions",{}).values()
    )
    current_heat_eur = equity * portfolio_heat_pct(state)/100.0
    projected_heat_pct = ((current_heat_eur + max(0.0, proposed_risk_eur)) / equity * 100.0) if equity > 0 else 999

    if projected_heat_pct > auto["max_portfolio_heat_pct"]:
        return False, f"Portefeuillerisico zou {projected_heat_pct:.2f}% worden"

    return True, "OK"
