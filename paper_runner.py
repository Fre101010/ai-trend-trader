from datetime import datetime, timezone
from trading_core import CFG, market_snapshot, desired_action, size_for_risk
from storage import load_state, save_state, save_portfolio_state, StorageUnavailable, acquire_run_lock, release_run_lock
from notifier import notify
from analytics import current_equity, portfolio_integrity
from risk_guard import clamp_settings

def add_event(p, kind, asset, message, extra=None, do_notify=True):
    event={
        "time":datetime.now(timezone.utc).isoformat(),
        "kind":kind,
        "asset":asset,
        "message":message,
        "extra":extra or {}
    }
    p.setdefault("events",[]).append(event)
    p["events"]=p["events"][-500:]
    if do_notify:
        notify(message)

def position_pnl(pos, price):
    side=pos.get("side","LONG")
    qty=float(pos.get("qty",0))
    entry=float(pos.get("entry",0))
    if side=="SHORT":
        return (entry-price)*qty
    return (price-entry)*qty


def close_position(p, portfolio_id, asset, price, reason="manual_close", do_notify=True):
    positions=p.setdefault("positions",{})
    trades=p.setdefault("trades",[])
    pos=positions.get(asset)
    if not pos:
        return None

    fee=CFG["execution"]["fee_rate"]
    slip=CFG["execution"]["slippage"]
    side=pos.get("side","LONG")

    if side=="SHORT":
        exit_px=price*(1+slip)
        margin=float(pos.get("margin_reserved",pos["entry"]*pos["qty"]))
        exit_notional=pos["qty"]*exit_px
        exit_fee=exit_notional*fee
        pnl=(pos["entry"]-exit_px)*pos["qty"]-exit_fee-pos.get("entry_fee",0)
        p["cash"] += margin + pnl
    else:
        exit_px=price*(1-slip)
        gross=pos["qty"]*exit_px
        exit_fee=gross*fee
        pnl=(exit_px-pos["entry"])*pos["qty"]-exit_fee-pos.get("entry_fee",0)
        p["cash"] += gross-exit_fee

    trade={
        "asset":asset,
        "portfolio":portfolio_id,
        "strategy_mode":pos.get("strategy_mode",portfolio_id),
        "side":side,
        "entry_time":pos["entry_time"],
        "exit_time":datetime.now(timezone.utc).isoformat(),
        "entry":pos["entry"],
        "exit":exit_px,
        "qty":pos["qty"],
        "pnl":pnl,
        "reason":reason,
        "max_r_reached":pos.get("max_r_reached",0.0),
    }
    trades.append(trade)
    del positions[asset]

    label="HANDMATIG" if reason=="manual_close" else reason.upper()
    add_event(
        p,
        "EXIT",
        asset,
        f"🛑 PAPER {side} EXIT — {portfolio_id.upper()} — {asset}\n"
        f"Reden: {label}\nResultaat: €{pnl:.2f}",
        trade,
        do_notify
    )
    return trade

def run_portfolio(p, portfolio_id):
    mode = "swing" if portfolio_id=="swing" else "active"
    fee=CFG["execution"]["fee_rate"]
    slip=CFG["execution"]["slippage"]

    positions=p.setdefault("positions",{})
    trades=p.setdefault("trades",[])
    enabled=p.setdefault("enabled_assets",{})
    auto=clamp_settings(p.setdefault("automation",{}))

    for asset,meta in CFG["portfolio"]["assets"].items():
        enabled.setdefault(asset,True)

        snap=market_snapshot(asset,mode)
        action=desired_action(asset,snap,mode)
        price=snap["1h"]["price"] if mode=="swing" else snap["15m"]["price"]
        prof=CFG["profiles"][meta["profile"]]
        pos=positions.get(asset)

        # ----- manage existing position -----
        if pos:
            side=pos.get("side","LONG")
            atr_src=snap["1d"]["atr"] if mode=="swing" else snap["1h"]["atr"]

            entry=float(pos["entry"])
            initial_stop=float(pos.get("initial_stop",pos["trail_stop"]))
            initial_risk=float(pos.get("initial_risk",abs(entry-initial_stop)))
            if initial_risk<=0:
                initial_risk=abs(entry-initial_stop) or max(entry*0.005,1e-9)

            favorable_move=(entry-price) if side=="SHORT" else (price-entry)
            current_r=favorable_move/initial_risk
            pos["current_r"]=current_r
            pos["max_r_reached"]=max(float(pos.get("max_r_reached",current_r)),current_r)

            trail_mult=prof["trail_atr"] if mode=="swing" else 2.0
            if mode=="active" and pos["max_r_reached"]>=2.0:
                trail_mult=1.5
                pos["profit_lock_stage"]="2R_TIGHT_TRAIL"

            old_trail=float(pos["trail_stop"])
            be_buffer=entry*((2*fee)+(2*slip))

            if side=="SHORT":
                candidate=price+trail_mult*atr_src
                new_trail=min(old_trail,candidate)
                if pos["max_r_reached"]>=1.0:
                    new_trail=min(new_trail,entry-be_buffer)
                    if pos.get("profit_lock_stage")!="2R_TIGHT_TRAIL":
                        pos["profit_lock_stage"]="1R_BREAK_EVEN"
                stop_hit=price>=new_trail
                trend_exit=(mode=="active" and not (snap["4h"]["trend"]=="BEARISH" and snap["1h"]["trend"]=="BEARISH"))
            else:
                candidate=price-trail_mult*atr_src
                new_trail=max(old_trail,candidate)
                if pos["max_r_reached"]>=1.0:
                    new_trail=max(new_trail,entry+be_buffer)
                    if pos.get("profit_lock_stage")!="2R_TIGHT_TRAIL":
                        pos["profit_lock_stage"]="1R_BREAK_EVEN"
                stop_hit=price<=new_trail
                if mode=="swing":
                    trend_exit=not (snap["1d"]["trend"]=="BULLISH" and snap["4h"]["trend"]=="BULLISH")
                else:
                    trend_exit=not (snap["4h"]["trend"]=="BULLISH" and snap["1h"]["trend"]=="BULLISH")

            pos["trail_stop"]=new_trail
            pos["last_price"]=price
            pos["unrealized_pnl"]=position_pnl(pos,price)

            if trend_exit or stop_hit:
                reason="trend_exit" if trend_exit else "trailing_stop"
                close_position(p,portfolio_id,asset,price,reason=reason,do_notify=True)
                pos=None

        # ----- open new position -----
        if (
            pos is None
            and enabled.get(asset,True)
            and action in ["LONG","SHORT"]
            and auto.get("mode","auto_paper")=="auto_paper"
        ):
            # Swing remains long-only by design.
            if mode=="swing" and action=="SHORT":
                continue

            if auto.get("emergency_stop"):
                continue

            if len(positions)>=int(auto.get("max_open_positions",5)):
                continue

            allocation=float(p.get("cash",0))*float(meta.get("allocation_weight",0.2))
            atr_src=snap["1d"]["atr"] if mode=="swing" else snap["1h"]["atr"]
            stop_mult=prof["initial_stop_atr"] if mode=="swing" else 1.6

            if action=="SHORT":
                stop=price+stop_mult*atr_src
            else:
                stop=price-stop_mult*atr_src

            qty=size_for_risk(
                allocation,
                price,
                stop,
                meta.get("risk_multiplier",1.0),
                auto.get("risk_per_trade_pct",0.5)
            )

            reserve=current_equity(p)*float(auto.get("min_cash_reserve_pct",12.5))/100.0

            if action=="SHORT":
                entry=price*(1-slip)
                notional=qty*entry
                entry_fee=notional*fee
                margin_reserved=notional
                cash_needed=margin_reserved+entry_fee

                if qty>0 and cash_needed <= max(0,float(p.get("cash",0))-reserve):
                    p["cash"] -= cash_needed
                    positions[asset]={
                        "entry_time":datetime.now(timezone.utc).isoformat(),
                        "portfolio":portfolio_id,
                        "strategy_mode":mode,
                        "side":"SHORT",
                        "entry":entry,
                        "qty":qty,
                        "initial_stop":stop,
                        "initial_risk":abs(entry-stop),
                        "trail_stop":stop,
                        "current_r":0.0,
                        "max_r_reached":0.0,
                        "profit_lock_stage":"NONE",
                        "entry_fee":entry_fee,
                        "last_price":price,
                        "margin_reserved":margin_reserved,
                        "unrealized_pnl":0.0
                    }
                    add_event(
                        p,
                        "ENTRY",
                        asset,
                        f"🔴 PAPER SHORT OPEN — {portfolio_id.upper()} — {asset}\nEntry: {entry:.2f}\nStop: {stop:.2f}",
                        {},
                        True
                    )

            else:
                entry=price*(1+slip)
                notional=qty*entry
                entry_fee=notional*fee

                if qty>0 and notional+entry_fee <= max(0,float(p.get("cash",0))-reserve):
                    p["cash"] -= notional+entry_fee
                    positions[asset]={
                        "entry_time":datetime.now(timezone.utc).isoformat(),
                        "portfolio":portfolio_id,
                        "strategy_mode":mode,
                        "side":"LONG",
                        "entry":entry,
                        "qty":qty,
                        "initial_stop":stop,
                        "initial_risk":abs(entry-stop),
                        "trail_stop":stop,
                        "current_r":0.0,
                        "max_r_reached":0.0,
                        "profit_lock_stage":"NONE",
                        "entry_fee":entry_fee,
                        "last_price":price,
                        "unrealized_pnl":0.0
                    }
                    add_event(
                        p,
                        "ENTRY",
                        asset,
                        f"🟢 PAPER LONG OPEN — {portfolio_id.upper()} — {asset}\nEntry: {entry:.2f}\nStop: {stop:.2f}",
                        {},
                        True
                    )

    p.setdefault("equity_history",[]).append({
        "time":datetime.now(timezone.utc).isoformat(),
        "equity":round(current_equity(p),2)
    })
    p["equity_history"]=p["equity_history"][-2000:]

def run_once(target="both"):
    lock_holder=acquire_run_lock()
    if not lock_holder:
        # Another runner is already processing the portfolio.
        state,mode=load_state()
        return state,"locked-skip"

    try:
            state,mode=load_state()

            reset_version=str(state.get("repair_info",{}).get("version",""))
            reset_mode=str(state.get("repair_info",{}).get("mode",""))
            if reset_version!="2.5.0" or reset_mode!="clean_reset":
                raise RuntimeError(
                    "Eenmalige clean reset v2.5.0 vereist voordat automatische trading opnieuw start."
                )

            # Block automated trading if book capital is obviously inconsistent.
            integrity=portfolio_integrity(state)
            if not integrity["ok"]:
                raise RuntimeError(
                    f"Portfolio-integriteit mislukt: afwijking €{integrity['delta']:.2f}. "
                    "Runner gestopt om verdere state-corruptie te voorkomen."
                )

            # Automated trading must never act on a stale/read-only fallback state.
            if str(mode).startswith("cache-readonly"):
                raise StorageUnavailable(
                    "Runner gestopt: Supabase is tijdelijk niet leesbaar. "
                    "Geen trades geopend/gesloten op basis van cached data."
                )

            if target=="swing":
                targets=["swing"]
            elif target=="active":
                targets=["active"]
            else:
                targets=["swing","active"]

            for pid in targets:
                # Work on the latest copy of this portfolio.
                current_state,current_mode=load_state()
                if str(current_mode).startswith("cache-readonly"):
                    raise StorageUnavailable(
                        f"{pid} runner gestopt: persistent state is tijdelijk niet beschikbaar."
                    )
                portfolio=current_state["portfolios"][pid]
                run_portfolio(portfolio,pid)

                # Save ONLY this portfolio into the freshest global state so the other
                # portfolio cannot be overwritten by a stale workflow.
                save_portfolio_state(
                    pid,
                    portfolio,
                    last_run=datetime.now(timezone.utc).isoformat()
                )

            final_state,final_mode=load_state()
            return final_state,final_mode
    finally:
        release_run_lock(lock_holder)

if __name__=="__main__":
    import sys
    target=sys.argv[1].lower() if len(sys.argv)>1 else "both"
    if target not in ["swing","active","both"]:
        target="both"
    s,m=run_once(target)
    print(f"paper run complete ({target})",m)
