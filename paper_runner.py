from datetime import datetime, timezone
from trading_core import CFG, market_snapshot, desired_action, size_for_risk
from storage import load_state, save_state
from notifier import notify

def add_event(state, kind, asset, message, extra=None, do_notify=True):
    event = {
        "time": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "asset": asset,
        "message": message,
        "extra": extra or {}
    }
    state.setdefault("events", []).append(event)
    state["events"] = state["events"][-500:]
    if do_notify:
        notify(message)

def run_once():
    state,mode = load_state()
    if not state.get("cash"):
        state["cash"] = float(CFG["starting_cash"])

    fee = CFG["execution"]["fee_rate"]
    slip = CFG["execution"]["slippage"]
    positions = state.setdefault("positions", {})
    trades = state.setdefault("trades", [])
    total_equity = state["cash"]

    for asset,meta in CFG["portfolio"]["assets"].items():
        snap = market_snapshot(asset)
        price = snap["1d"]["price"]
        action = desired_action(asset,snap)
        p = CFG["profiles"][meta["profile"]]
        pos = positions.get(asset)

        if pos:
            old_trail = pos["trail_stop"]
            new_trail = max(old_trail, price - p["trail_atr"]*snap["1d"]["atr"])
            pos["trail_stop"] = new_trail
            pos["last_price"] = price
            pos["unrealized_pnl"] = (price-pos["entry"])*pos["qty"]

            if old_trail > 0 and new_trail > old_trail * 1.0025:
                msg = f"📈 PAPER TRAIL UPDATE — {asset}\nNieuwe trailing stop: {new_trail:.2f}\nKoers: {price:.2f}\nOpen P/L: €{pos['unrealized_pnl']:.2f}"
                add_event(state,"TRAIL_UPDATE",asset,msg,{"old_trail":old_trail,"new_trail":new_trail},True)

            trend_exit = not (snap["1d"]["trend"]=="BULLISH" and snap["4h"]["trend"]=="BULLISH")
            stop_hit = price <= new_trail

            if trend_exit or stop_hit:
                exit_px = price*(1-slip)
                gross = pos["qty"]*exit_px
                exit_fee = gross*fee
                pnl = (exit_px-pos["entry"])*pos["qty"] - exit_fee - pos.get("entry_fee",0)
                state["cash"] += gross-exit_fee
                reason = "trend_exit" if trend_exit else "trailing_stop"
                trade = {
                    "asset":asset,"entry_time":pos["entry_time"],
                    "exit_time":datetime.now(timezone.utc).isoformat(),
                    "entry":pos["entry"],"exit":exit_px,"qty":pos["qty"],
                    "pnl":pnl,"reason":reason
                }
                trades.append(trade)
                msg = f"🛑 PAPER EXIT — {asset}\nReden: {reason}\nEntry: {pos['entry']:.2f}\nExit: {exit_px:.2f}\nResultaat: €{pnl:.2f}"
                add_event(state,"EXIT",asset,msg,trade,True)
                del positions[asset]
                pos = None
            else:
                total_equity += pos["qty"]*price

        if pos is None and action=="LONG":
            allocation = state["cash"]*meta["allocation_weight"]
            stop = price-p["initial_stop_atr"]*snap["1d"]["atr"]
            qty = size_for_risk(allocation,price,stop)
            entry = price*(1+slip)
            notional = qty*entry
            entry_fee = notional*fee
            if qty>0 and notional+entry_fee <= state["cash"]:
                state["cash"] -= notional+entry_fee
                positions[asset] = {
                    "entry_time":datetime.now(timezone.utc).isoformat(),
                    "entry":entry,"qty":qty,"initial_stop":stop,
                    "trail_stop":stop,"entry_fee":entry_fee,
                    "last_price":price,"unrealized_pnl":0.0
                }
                total_equity += qty*price
                msg = f"🟢 PAPER LONG OPEN — {asset}\nEntry: {entry:.2f}\nInitial stop: {stop:.2f}\nPositiewaarde: €{notional:.2f}"
                add_event(state,"ENTRY",asset,msg,{"entry":entry,"stop":stop,"qty":qty,"notional":notional},True)

    state["equity_history"].append({
        "time": datetime.now(timezone.utc).isoformat(),
        "equity": round(total_equity,2)
    })
    state["equity_history"] = state["equity_history"][-2000:]
    mode = save_state(state)
    return state,mode

if __name__=="__main__":
    state,mode = run_once()
    print("paper run complete:", mode, "cash=", round(state["cash"],2), "open=", list(state["positions"].keys()))
