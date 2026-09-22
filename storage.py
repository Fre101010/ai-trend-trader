from __future__ import annotations
import os, json
from pathlib import Path
from datetime import datetime, timezone

LOCAL = Path("paper_state.json")

def _get_secret(name):
    val = os.getenv(name)
    if val:
        return val.strip()
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name]).strip()
    except Exception:
        pass
    return None

def get_secret(name):
    return _get_secret(name)

def _supabase():
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_KEY")
    if not url or not key:
        return None
    url = url.rstrip("/")
    if "/rest/v1" in url:
        url = url.split("/rest/v1")[0]
    from supabase import create_client
    return create_client(url, key)

def portfolio_template(cash=0.0):
    return {
        "cash": float(cash),
        "positions": {},
        "trades": [],
        "events": [],
        "equity_history": [],
        "enabled_assets": {},
        "automation": {
            "mode": "auto_paper",
            "live_enabled": False,
            "emergency_stop": False,
            "max_open_positions": 5,
            "max_daily_loss_pct": 2.0,
            "risk_per_trade_pct": 0.5,
            "require_stop": True,
            "max_portfolio_heat_pct": 2.0,
            "min_cash_reserve_pct": 12.5,
            "account_capital": float(cash),
        }
    }

def default_state():
    return {
        "version": 2,
        "portfolios": {
            "swing": portfolio_template(5000.0),
            "active": portfolio_template(0.0),
        },
        "transfers": [],
        "last_run": None,
        "last_daily_summary_date": None,
    }

def _legacy_to_v2(state):
    # Existing v1.x portfolio becomes Swing. Active starts at zero.
    swing = portfolio_template(float(state.get("cash", 5000.0)))
    for key in ["cash","positions","trades","events","equity_history","enabled_assets","automation"]:
        if key in state:
            swing[key] = state[key]
    swing["automation"].setdefault("account_capital", 5000.0)

    return {
        "version": 2,
        "portfolios": {
            "swing": swing,
            "active": portfolio_template(0.0),
        },
        "transfers": [],
        "last_run": state.get("last_run"),
        "last_daily_summary_date": state.get("last_daily_summary_date"),
    }

def normalize_state(state):
    if not isinstance(state, dict):
        return default_state()

    if "portfolios" not in state:
        state = _legacy_to_v2(state)

    state.setdefault("version", 2)
    state.setdefault("transfers", [])
    state.setdefault("last_run", None)
    state.setdefault("last_daily_summary_date", None)
    state.setdefault("portfolios", {})

    for pid, default_cash in [("swing",5000.0),("active",0.0)]:
        p = state["portfolios"].setdefault(pid, portfolio_template(default_cash))
        base = portfolio_template(default_cash)
        for k,v in base.items():
            p.setdefault(k,v)
        # ensure automation keys
        for k,v in base["automation"].items():
            p["automation"].setdefault(k,v)

    return state

def load_state():
    sb = _supabase()
    if sb:
        try:
            res = sb.table("paper_state").select("*").eq("id", 1).execute()
            if res.data:
                return normalize_state(res.data[0]["payload"]), "supabase"
            state = default_state()
            sb.table("paper_state").upsert({"id": 1, "payload": state}).execute()
            return state, "supabase"
        except Exception as e:
            return default_state(), f"supabase-error:{type(e).__name__}"

    if LOCAL.exists():
        try:
            return normalize_state(json.loads(LOCAL.read_text(encoding="utf-8"))), "local-demo"
        except Exception:
            pass
    return default_state(), "new"

def save_state(state, update_last_run=True):
    state = normalize_state(state)
    if update_last_run:
        state["last_run"] = datetime.now(timezone.utc).isoformat()
    sb = _supabase()
    if sb:
        try:
            sb.table("paper_state").upsert({"id": 1, "payload": state}).execute()
            return "supabase"
        except Exception:
            LOCAL.write_text(json.dumps(state, indent=2), encoding="utf-8")
            return "local-demo"
    LOCAL.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return "local-demo"


def save_portfolio_state(portfolio_id, portfolio_state, last_run=None):
    """
    Merge-safe save for one portfolio.
    Reloads the newest persisted state first, replaces only the requested
    portfolio, and preserves the other portfolio/transfers/global fields.
    """
    latest,_ = load_state()
    latest = normalize_state(latest)
    latest["portfolios"][portfolio_id] = portfolio_state
    if last_run is not None:
        latest["last_run"] = last_run
    return save_state(latest, update_last_run=(last_run is None))
