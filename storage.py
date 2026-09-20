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

def default_state():
    return {
        "cash": 5000.0,
        "positions": {},
        "trades": [],
        "events": [],
        "equity_history": [],
        "last_run": None
    }

def normalize_state(state):
    base = default_state()
    for k,v in base.items():
        state.setdefault(k, v)
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

def save_state(state):
    state = normalize_state(state)
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
