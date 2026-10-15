"""Manager: scans, rebalances the index, proposes or performs listings and delistings."""
import time

from . import index as gindex
from . import state
from .config import CFG
from .listing import halt_market, list_coin
from .scanner import run_scan

DCFG = CFG["delisting"]
MCFG = CFG["manager"]


def check_delistings(cands: dict) -> None:
    now = int(time.time())
    for coin, m in state.load("markets").items():
        if m.get("kind") != "single" or m.get("status") != "live":
            continue
        c = cands.get(m["mint"])
        if not c:
            continue
        tcfg = CFG["tiers"][m.get("tier", "tier1")]
        hours = DCFG["below_threshold_hours"]
        window = [h for h in c.get("history", []) if h[0] >= now - hours * 3600]
        covered = bool(window) and now - window[0][0] >= hours * 3600 * 0.9
        reason = None
        if covered and max(h[1] for h in window) < DCFG["below_threshold_ratio"] * tcfg["min_mcap_usd"]:
            reason = f"market cap below {DCFG['below_threshold_ratio']:.0%} of the tier threshold for {hours}h"
        elif c["liquidity_usd"] < DCFG["min_liquidity_ratio"] * tcfg["min_liquidity_usd"]:
            reason = f"pool liquidity down to ${c['liquidity_usd']:,.0f}"
        if reason:
            if DCFG["auto_halt"]:
                halt_market(coin, reason)
            else:
                state.log_event("delist?", f"{coin}: delisting recommended ({reason})")


def handle_listings(cands: dict) -> None:
    markets = state.load("markets")
    if CFG["index"]["symbol"] not in markets:
        return
    listed = {m.get("mint") for m in markets.values()}
    singles = sum(1 for m in markets.values() if m.get("kind") == "single" and m.get("status") == "live")
    ready = [c for c in cands.values() if c.get("tier") in ("tier1", "tier2") and c["mint"] not in listed]
    ready.sort(key=lambda c: c["liquidity_usd"], reverse=True)
    for c in ready:
        if MCFG["auto_list_tier1"] and singles < MCFG["max_single_perps"]:
            try:
                coin = list_coin(c["mint"])
                singles += 1
                state.log_event("listing", f"Auto-listed {coin}")
            except (SystemExit, RuntimeError) as e:
                state.log_event("error", f"Listing {c['symbol']} failed: {e}")
        else:
            flagged = state.load("flags")
            if c["mint"] not in flagged:
                state.log_event("candidate", f"{c['symbol']} qualifies for its own perp: python -m hip3 list {c['mint']}")
                flagged[c["mint"]] = int(time.time())
                state.save("flags", flagged)


def run_once() -> None:
    cands = run_scan(verbose=False)
    gindex.rebalance(cands)
    check_delistings(cands)
    handle_listings(cands)


def run_forever() -> None:
    from .watchdog import start_thread

    start_thread()
    state.log_event("manager", f"Manager started: scan every {MCFG['scan_interval_min']} min, oracle watchdog on")
    while True:
        started = time.time()
        try:
            run_once()
        except Exception as e:
            state.log_event("error", f"Manager cycle failed: {e}")
        time.sleep(max(10, MCFG["scan_interval_min"] * 60 - (time.time() - started)))
