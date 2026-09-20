from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from trading_core import CFG, market_snapshot, desired_action, size_for_risk
from storage import load_state, save_state
from notifier import notify
from analytics import current_equity, realized_pnl, open_pnl, trade_stats, max_drawdown_pct, return_since_start_pct

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

def maybe_send_daily_summary(state):
    now_local = datetime.now(ZoneInfo("Europe/Brussels"))
    today = now_local.date().isoformat()
    # Designed to run once in the evening from GitHub Actions.
    if state.get("last_daily_summary_date") == today:
        return False

    stats = trade_stats(state)
    pf = stats["profit_factor"]
    pf_text = "∞" if pf == float("inf") else f"{pf:.2f}"
    eq = current_equity(state)
    msg = (
        f"📊 AI Trend Trader — dagelijkse paper samenvatting\n"
        f"Datum: {today}\n"
        f"Equity: €{eq:,.2f}\n"
        f"Cash: €{state.get('cash',0):,.2f}\n"
        f"Open P/L: €{open_pnl(state):,.2f}\n"
        f"Gerealiseerd P/L: €{realized_pnl(state):,.2f}\n"
        f"Rendement sinds start: {return_since_start_pct(state):+.2f}%\n"
        f"Max drawdown: {max_drawdown_pct(state):.2f}%\n"
        f"Gesloten trades: {stats['count']}\n"
        f"Winrate: {stats['winrate']:.1f}%\n"
        f"Profit factor: {pf_text}\n"
        f"Open posities: {len(state.get('positions',{}))}"
    )
    ok,_ = notify(msg)
    if ok:
        state["last_daily_summary_date"] = today
        add_event(state, "DAILY_SUMMARY", "PORTFOLIO", msg, do_notify=False)
        return True
    return False

def run_once(send_daily_summary=False):
    state,mode = load_state()
    if not state.get("cash"):
        state["cash"] = float(CFG["starting_cash"])
    state.setdefault("starting_equity", float(CFG["starting_cash"]))

    fee = CFG["execution"]["fee_rate"]
    slip = CFG["execution"]["slippage"]
    positions = state.setdefault("positions", {})
    trades = state.setdefault("trades", [])

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
                msg = f"🟢 PAPER LONG OPEN — {asset}\nEntry: {entry:.2f}\nInitial stop: {stop:.2f}\nPositiewaarde: €{notional:.2f}"
                add_event(state,"ENTRY",asset,msg,{"entry":entry,"stop":stop,"qty":qty,"notional":notional},True)

    total_equity = current_equity(state)
    state.setdefault("equity_history", []).append({
        "time": datetime.now(timezone.utc).isoformat(),
        "equity": round(total_equity,2)
    })
    state["equity_history"] = state["equity_history"][-2000:]

    if send_daily_summary:
        maybe_send_daily_summary(state)

    mode = save_state(state)
    return state,mode

if __name__=="__main__":
    state,mode = run_once()
    print("paper run complete:", mode, "cash=", round(state["cash"],2), "open=", list(state["positions"].keys()))
