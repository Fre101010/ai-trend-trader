from copy import deepcopy
from datetime import datetime, timezone
from storage import load_state, save_state, StorageUnavailable
from trading_core import CFG

KNOWN = {
    "nasdaq": {
        "asset": "Nasdaq 100 ETF",
        "entry": 721.67,
        "qty": 0.4193548387,   # reconstructed from earlier saved P/L
        "trail_stop": 702.88,
    },
    "sp500": {
        "asset": "S&P 500 ETF",
        "entry": 761.92,
        "qty": 0.5862068966,   # reconstructed from earlier saved P/L
        "trail_stop": 748.60,
    },
}

def repair_state():
    state,mode=load_state()
    if str(mode).startswith("cache-readonly"):
        raise StorageUnavailable("Herstel geweigerd: Supabase staat in read-only cachemodus.")

    backup=deepcopy(state)

    swing=state["portfolios"]["swing"]
    active=state["portfolios"]["active"]

    # Preserve Active exactly as-is.
    active_copy=deepcopy(active)

    # Rebuild Swing around the known pre-corruption situation.
    old_positions=swing.get("positions",{})
    rebuilt={}

    for item in KNOWN.values():
        asset=item["asset"]
        existing=old_positions.get(asset,{})
        entry=item["entry"]
        qty=item["qty"]
        trail=item["trail_stop"]

        rebuilt[asset]={
            "entry_time": existing.get("entry_time","2026-09-20T08:18:41+00:00"),
            "portfolio":"swing",
            "strategy_mode":"swing",
            "side":"LONG",
            "entry":entry,
            "qty":qty,
            "initial_stop": existing.get("initial_stop",trail),
            "initial_risk": abs(entry-float(existing.get("initial_stop",trail))),
            "trail_stop": min(float(existing.get("trail_stop",trail)), trail)
                if float(existing.get("trail_stop",trail)) < entry else trail,
            "entry_fee": float(existing.get("entry_fee",0.0)),
            "last_price": float(existing.get("last_price",entry)),
            "unrealized_pnl": 0.0,
            "current_r": 0.0,
            "max_r_reached": 0.0,
            "profit_lock_stage":"NONE",
        }

    swing["positions"]=rebuilt

    # Known original transfer: €1,000 from Swing to Active.
    # Preserve Active cash/positions but restore total capital base to €5,000.
    # Compute Swing cash so combined book capital equals €5,000 before P/L.
    active_book_value=float(active_copy.get("cash",0.0))
    for pos in active_copy.get("positions",{}).values():
        side=pos.get("side","LONG")
        entry=float(pos.get("entry",0))
        qty=float(pos.get("qty",0))
        if side=="SHORT":
            active_book_value += float(pos.get("margin_reserved",entry*qty))
        else:
            active_book_value += entry*qty

    swing_positions_cost=sum(float(p["entry"])*float(p["qty"]) + float(p.get("entry_fee",0)) for p in rebuilt.values())

    # Base capital left for Swing = 5000 - Active book value.
    swing_book_target=5000.0-active_book_value
    swing["cash"]=max(0.0,swing_book_target-swing_positions_cost)

    # Restore the known realized gold loss.
    existing_trades=swing.get("trades",[])
    gold_found=any(t.get("asset")=="Goud" and abs(float(t.get("pnl",0))+1.30)<0.25 for t in existing_trades)
    if not gold_found:
        existing_trades.append({
            "asset":"Goud",
            "portfolio":"swing",
            "strategy_mode":"swing",
            "side":"LONG",
            "entry_time":"2026-09-20T08:18:41+00:00",
            "exit_time":"2026-09-21T11:48:00+00:00",
            "entry":4426.23,
            "exit":4392.35,
            "qty":0.03837,
            "pnl":-1.30,
            "reason":"historical_repair",
            "max_r_reached":0.0,
        })
    swing["trades"]=existing_trades

    # Reset equity history; old history mixed corrupted/default snapshots.
    swing["equity_history"]=[]
    active_copy["equity_history"]=[]
    state["portfolios"]["active"]=active_copy

    state["capital_ledger"]={
        "initial_total_capital":5000.0,
        "external_deposits":0.0,
        "external_withdrawals":0.0,
    }

    # Ensure transfer ledger contains the known €1,000 move exactly once.
    transfers=state.setdefault("transfers",[])
    if not any(
        t.get("from")=="swing" and t.get("to")=="active" and abs(float(t.get("amount",0))-1000.0)<0.01
        for t in transfers
    ):
        transfers.append({
            "time":"2026-09-21T13:00:00+00:00",
            "from":"swing",
            "to":"active",
            "amount":1000.0,
            "reason":"historical_repair",
        })

    state["repair_info"]={
        "repaired_at":datetime.now(timezone.utc).isoformat(),
        "version":"2.4.8",
        "note":"Recovered known Swing entries and €5,000 total capital baseline; Active preserved.",
    }

    save_state(state,update_last_run=False)
    return state,backup
