from __future__ import annotations
from risk_guard import clamp_settings
from dataclasses import dataclass
from typing import Dict, Any

MODES = {
    "signals": "Signalen",
    "confirm": "Handmatig bevestigen",
    "auto_paper": "Auto Paper",
    "auto_live": "Auto Live",
}

DEFAULT_AUTOMATION = {
    "mode": "auto_paper",
    "live_enabled": False,
    "emergency_stop": False,
    "max_open_positions": 5,
    "max_daily_loss_pct": 2.0,
    "risk_per_trade_pct": 0.5,
    "require_stop": True,
    "max_portfolio_heat_pct": 2.0,
    "min_cash_reserve_pct": 12.5,
    "account_capital": 5000.0,
}

def normalize_automation(state: Dict[str, Any]) -> Dict[str, Any]:
    cfg = state.setdefault("automation", {})
    for k, v in DEFAULT_AUTOMATION.items():
        cfg.setdefault(k, v)
    cfg.update(clamp_settings(cfg))
    return cfg

def can_open_new_trade(state: Dict[str, Any], open_positions: int) -> tuple[bool, str]:
    cfg = normalize_automation(state)
    if cfg.get("emergency_stop"):
        return False, "Noodstop actief"
    if open_positions >= int(cfg.get("max_open_positions", 5)):
        return False, "Maximum aantal open posities bereikt"
    if cfg.get("mode") == "signals":
        return False, "Signaalmodus: geen automatische entries"
    if cfg.get("mode") == "confirm":
        return False, "Bevestigingsmodus: gebruiker moet entry bevestigen"
    if cfg.get("mode") == "auto_live" and not cfg.get("live_enabled"):
        return False, "Auto Live is vergrendeld"
    return True, "OK"

class BrokerAdapter:
    name = "Niet gekoppeld"

    def is_ready(self) -> bool:
        return False

    def open_long(self, symbol: str, qty: float, stop: float | None = None):
        raise RuntimeError("Geen live broker gekoppeld.")

    def close_position(self, symbol: str):
        raise RuntimeError("Geen live broker gekoppeld.")

def broker_status(state: Dict[str, Any]) -> Dict[str, Any]:
    cfg = normalize_automation(state)
    return {
        "mode": cfg["mode"],
        "mode_label": MODES.get(cfg["mode"], cfg["mode"]),
        "live_enabled": bool(cfg.get("live_enabled")),
        "emergency_stop": bool(cfg.get("emergency_stop")),
        "broker": "Nog niet gekoppeld",
        "live_ready": False,
    }
