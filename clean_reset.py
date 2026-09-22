from datetime import datetime, timezone
from storage import load_state, save_state, portfolio_template, StorageUnavailable

RESET_VERSION = "2.5.0"

def clean_reset():
    state, mode = load_state()

    if str(mode).startswith("cache-readonly"):
        raise StorageUnavailable(
            "Supabase is tijdelijk niet betrouwbaar bereikbaar. Reset niet uitgevoerd."
        )

    # Known correct accounting baseline:
    # Start capital €5,000
    # Known realized Gold result -€1.30
    # So total paper equity after preserving that historical result = €4,998.70.
    #
    # We keep the user's intended allocation:
    # Swing €3,998.70
    # Active €1,000.00
    #
    # No open positions are carried over. This intentionally removes any
    # corrupted / reconstructed trades from the previous broken state.
    swing = portfolio_template(3998.70)
    active = portfolio_template(1000.00)

    # Preserve user asset enable/disable preferences where possible.
    old_swing = state.get("portfolios",{}).get("swing",{})
    old_active = state.get("portfolios",{}).get("active",{})
    swing["enabled_assets"] = dict(old_swing.get("enabled_assets",{}))
    active["enabled_assets"] = dict(old_active.get("enabled_assets",{}))

    # Preserve automation settings, but keep paper-only safety.
    if old_swing.get("automation"):
        swing["automation"].update(old_swing["automation"])
    if old_active.get("automation"):
        active["automation"].update(old_active["automation"])

    swing["automation"]["live_enabled"] = False
    active["automation"]["live_enabled"] = False
    swing["automation"]["account_capital"] = 3998.70
    active["automation"]["account_capital"] = 1000.00

    # Preserve the one confirmed historical realized trade.
    swing["trades"] = [{
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
        "reason":"historical_confirmed",
        "max_r_reached":0.0,
    }]

    state["portfolios"] = {
        "swing": swing,
        "active": active,
    }

    state["capital_ledger"] = {
        "initial_total_capital": 5000.0,
        "external_deposits": 0.0,
        "external_withdrawals": 0.0,
    }

    state["transfers"] = [{
        "time":"2026-09-21T13:00:00+00:00",
        "from":"swing",
        "to":"active",
        "amount":1000.0,
        "reason":"allocation_baseline",
    }]

    state["repair_required"] = False
    state["repair_info"] = {
        "version": RESET_VERSION,
        "repaired_at": datetime.now(timezone.utc).isoformat(),
        "mode": "clean_reset",
        "note": "Clean paper reset: €3,998.70 Swing + €1,000 Active; no open positions carried over."
    }

    # Restart forward-test history.
    state["last_run"] = None
    state["last_daily_summary_date"] = None

    save_state(state, update_last_run=False)
    return state
