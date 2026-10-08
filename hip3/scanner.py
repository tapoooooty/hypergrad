"""Graduate scanner: finds Solana memecoins, computes metrics and assigns tiers."""
import time

from . import state
from .config import CFG
from .sources import dexscreener, pumpfun
from .sources.solana_rpc import SolanaRPC

TIER_ORDER = ["tier2", "tier1", "tier0"]


def _usd(v: float) -> str:
    """Compact dollars: $6.8M, $720K."""
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if v >= div:
            return f"${v / div:.3g}{suf}"
    return f"${v:.0f}"


def _sustained(history: list, threshold: float, hours: float, now: int) -> bool:
    """Market cap stayed ≥ 70% of the threshold for the whole window, and the window is covered by samples."""
    if hours <= 0:
        return True
    if not history or now - min(h[0] for h in history) < hours * 3600 * 0.9:
        return False
    window = [h for h in history if h[0] >= now - hours * 3600]
    return bool(window) and min(h[1] for h in window) >= 0.7 * threshold


def classify(c: dict, now: int) -> tuple[str | None, list[str]]:
    """Returns (best tier or None, blockers for the next tier)."""
    safety = CFG["safety"]
    if safety["require_pump_fun_origin"] and not c["mint"].endswith("pump") and not c.get("pumpfun"):
        return None, ["not a pump.fun coin"]
    if c.get("price_change_1h_pct", 0) > safety["max_price_change_1h_pct"]:
        return None, [f"pumping +{c['price_change_1h_pct']:.0f}% in 1h"]
    if c.get("top10_pct") is not None and c["top10_pct"] > safety["max_top10_holders_pct"]:
        return None, [f"top-10 holders own {c['top10_pct']:.1f}%"]
    if c.get("dev_pct") is not None and c["dev_pct"] > safety["max_dev_holding_pct"]:
        return None, [f"dev wallet owns {c['dev_pct']:.1f}%"]

    reasons: list[str] = []
    age_h = (now * 1000 - c["created_ms"]) / 3_600_000 if c.get("created_ms") else 0
    for tier in TIER_ORDER:
        t = CFG["tiers"][tier]
        fails = []
        if c["mcap_usd"] < t["min_mcap_usd"]:
            fails.append(f"market cap {_usd(c['mcap_usd'])} of {_usd(t['min_mcap_usd'])}")
        if c["liquidity_usd"] < t["min_liquidity_usd"]:
            fails.append(f"liquidity {_usd(c['liquidity_usd'])} of {_usd(t['min_liquidity_usd'])}")
        if c["volume_24h_usd"] < t["min_volume_24h_usd"]:
            fails.append(f"volume {_usd(c['volume_24h_usd'])} of {_usd(t['min_volume_24h_usd'])}")
        if age_h < t["min_age_hours"]:
            fails.append(f"age {age_h:.0f}h of {t['min_age_hours']}h")
        if not fails and not _sustained(c.get("history", []), t["min_mcap_usd"], t["sustain_hours"], now):
            fails.append(f"holding {_usd(t['min_mcap_usd'])} for {t['sustain_hours']}h")
        if not fails:
            return tier, reasons
        reasons = fails
    return None, reasons


def run_scan(verbose: bool = True) -> dict:
    now = int(time.time())
    cands: dict = state.load("candidates")

    # 1. Discovery
    pf = {c["mint"]: c for c in pumpfun.graduated_coins(CFG["sources"]["pumpfun_pages"])}
    mints = {m for m in set(pf) | dexscreener.discover_mints() | set(cands) if m}
    if CFG["safety"]["require_pump_fun_origin"]:
        mints = {m for m in mints if m.endswith("pump") or m in pf}

    # 2. Market metrics
    pairs = dexscreener.pairs_for_tokens(sorted(mints))
    rpc = SolanaRPC(CFG["sources"]["solana_rpc"])
    for mint, ps in pairs.items():
        s = dexscreener.summarize(ps)
        if not s:
            continue
        prev = cands.get(mint, {})
        c = {**prev, **s}
        c["pumpfun"] = mint in pf or prev.get("pumpfun", False)
        if mint in pf:
            c["creator"] = pf[mint].get("creator")
            c["created_ms"] = pf[mint].get("created_ms") or s["first_pair_ms"]
        else:
            c["created_ms"] = prev.get("created_ms") or s["first_pair_ms"]
        hist = [h for h in prev.get("history", []) if h[0] >= now - 8 * 86400]
        hist.append([now, round(s["mcap_usd"]), round(s["liquidity_usd"])])
        c["history"] = hist[-1500:]
        c["updated_at"] = now

        # 3. Holders: only for coins above the tier-0 market cap (saves RPC calls)
        if CFG["safety"]["check_holders"] and s["mcap_usd"] >= CFG["tiers"]["tier0"]["min_mcap_usd"]:
            if now - prev.get("holders_checked_at", 0) > 6 * 3600:
                try:
                    c["top10_pct"] = round(rpc.top10_pct(mint), 2)
                    if c.get("creator"):
                        c["dev_pct"] = round(rpc.wallet_pct(c["creator"], mint), 2)
                    c["holders_checked_at"] = now
                except Exception as e:  # public RPCs rate-limit aggressively
                    c["holders_error"] = str(e)[:200]

        tier, reasons = classify(c, now)
        old_tier = prev.get("tier")
        c["tier"] = tier
        c["next_tier_blockers"] = reasons
        if tier != old_tier and (tier or old_tier):
            state.log_event("tier", f"{c['symbol']} moved from {old_tier or 'watch'} to {tier or 'watch'}", mint=mint)
        cands[mint] = c

    # Drop dead and tiny coins, except those trading on our DEX
    live_mints = {m.get("mint") for m in state.load("markets").values()}
    cands = {
        m: c
        for m, c in cands.items()
        if m in live_mints or c.get("tier") or c.get("mcap_usd", 0) >= 0.3 * CFG["tiers"]["tier0"]["min_mcap_usd"]
    }
    state.save("candidates", cands)

    if verbose:
        ranked = sorted(cands.values(), key=lambda c: c.get("mcap_usd", 0), reverse=True)
        print(f"{'TICKER':<10}{'MCAP':>14}{'LIQ':>12}{'VOL 24H':>14}  TIER   BLOCKERS")
        for c in ranked[:40]:
            print(
                f"{c['symbol'][:9]:<10}{c['mcap_usd']:>14,.0f}{c['liquidity_usd']:>12,.0f}"
                f"{c['volume_24h_usd']:>14,.0f}  {c.get('tier') or 'watch':<6} {'; '.join(c.get('next_tier_blockers', [])[:2])}"
            )
    return cands
