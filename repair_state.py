from copy import deepcopy
from datetime import datetime, timezone
from storage import load_state, save_state, StorageUnavailable

REPAIR_VERSION="2.4.10"

KNOWN_SWING = {
    "Nasdaq 100 ETF": {
        "entry": 721.67,
        "trail_stop": 702.88,
        "qty": 0.4193548387,
        "entry_time": "2026-09-20T08:18:41+00:00",
    },
    "S&P 500 ETF": {
        "entry": 761.92,
        "trail_stop": 748.60,
        "qty": 0.5862068966,
        "entry_time": "2026-09-20T08:18:41+00:00",
    },
}

def repair_state():
    state,mode=load_state()
    if str(mode).startswith("cache-readonly"):
        raise StorageUnavailable("Herstel geweigerd: Supabase staat in read-only cachemodus.")

    active=deepcopy(state["portfolios"]["active"])
    swing=state["portfolios"]["swing"]

    # Keep Active exactly as persisted.
    state["portfolios"]["active"]=active

    rebuilt={}
    for asset,k in KNOWN_SWING.items():
        entry=float(k["entry"])
        qty=float(k["qty"])
        trail=float(k["trail_stop"])
        rebuilt[asset]={
            "entry_time":k["entry_time"],
            "portfolio":"swing",
            "strategy_mode":"swing",
            "side":"LONG",
            "entry":entry,
            "qty":qty,
            "initial_stop":trail,
            "initial_risk":abs(entry-trail),
            "trail_stop":trail,
            "entry_fee":0.0,
            "last_price":entry,
            "unrealized_pnl":0.0,
            "current_r":0.0,
            "max_r_reached":0.0,
            "profit_lock_stage":"NONE",
        }

    swing["positions"]=rebuilt

    # Only the known Gold realized trade remains in restored Swing history.
    swing["trades"]=[{
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
    }]

    state["capital_ledger"]={
        "initial_total_capital":5000.0,
        "external_deposits":0.0,
        "external_withdrawals":0.0,
    }

    # Book-value accounting:
    # combined cash + open positions at ENTRY/MARGIN value must equal
    # base capital + realized P/L - still-open entry fees.
    active_book=float(active.get("cash",0.0))
    active_open_fees=0.0
    for pos in active.get("positions",{}).values():
        entry=float(pos.get("entry",0))
        qty=float(pos.get("qty",0))
        active_open_fees += float(pos.get("entry_fee",0.0))
        if pos.get("side","LONG")=="SHORT":
            active_book += float(pos.get("margin_reserved",entry*qty))
        else:
            active_book += entry*qty

    swing_positions_book=sum(float(pos["entry"])*float(pos["qty"]) for pos in rebuilt.values())
    swing_open_fees=sum(float(pos.get("entry_fee",0.0)) for pos in rebuilt.values())

    realized_total=-1.30 + sum(float(t.get("pnl",0.0)) for t in active.get("trades",[]))
    total_open_fees=active_open_fees+swing_open_fees
    target_combined_book=5000.0+realized_total-total_open_fees

    swing["cash"]=target_combined_book-active_book-swing_positions_book
    if swing["cash"] < 0:
        raise RuntimeError(
            f"Herstelberekening geeft negatieve Swing cash: €{swing['cash']:.2f}"
        )

    swing["equity_history"]=[]
    active["equity_history"]=[]

    state["transfers"]=[{
        "time":"2026-09-21T13:00:00+00:00",
        "from":"swing",
        "to":"active",
        "amount":1000.0,
        "reason":"historical_repair",
    }]

    state["repair_required"]=False
    state["repair_info"]={
        "repaired_at":datetime.now(timezone.utc).isoformat(),
        "version":REPAIR_VERSION,
        "note":"Known-good Swing restoration; Active preserved; exact €5,000 accounting baseline.",
    }

    save_state(state,update_last_run=False)
    return state
