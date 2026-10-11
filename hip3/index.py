"""GRAD index: a basket of graduates with a chained level.

Between rebalances: level = Σ units_i × price_i.
At a rebalance:     units_i = level × w_i / price_i, so the level never jumps.
Weights ∝ √liquidity, capped at max_weight per coin.
"""
import math
import time

from . import state
from .config import CFG

ICFG = CFG["index"]


def _cap_weights(raw: dict[str, float], cap: float) -> dict[str, float]:
    """Normalize with a cap; the excess is redistributed to the remaining coins."""
    w = {k: v for k, v in raw.items() if v > 0}
    if not w:
        return {}
    cap = max(cap, 1.0 / len(w))
    fixed: dict[str, float] = {}
    for _ in range(len(w) + 1):
        free = {k: v for k, v in w.items() if k not in fixed}
        if not free:
            break
        budget = 1.0 - sum(fixed.values())
        total = sum(free.values())
        over = {k for k, v in free.items() if v / total * budget > cap}
        if not over:
            for k, v in free.items():
                fixed[k] = v / total * budget
            break
        for k in over:
            fixed[k] = cap
    return fixed


def select_components(cands: dict) -> dict[str, float]:
    eligible = [c for c in cands.values() if c.get("tier") in ("tier0", "tier1", "tier2") and c.get("price_usd")]
    eligible.sort(key=lambda c: c["liquidity_usd"], reverse=True)
    eligible = eligible[: ICFG["max_components"]]
    raw = {c["mint"]: math.sqrt(max(c["liquidity_usd"], 1.0)) for c in eligible}
    return _cap_weights(raw, ICFG["max_weight"])


def level_from_prices(idx: dict, prices: dict[str, float]) -> float | None:
    units = idx.get("units") or {}
    if not units:
        return None
    last = idx.get("last_prices", {})
    total = 0.0
    for mint, u in units.items():
        px = prices.get(mint) or last.get(mint)
        if px is None:
            return None
        total += u * px
    return total


def rebalance(cands: dict, prices: dict[str, float] | None = None, force: bool = False) -> dict:
    idx = state.load("index")
    now = int(time.time())
    if not force and idx.get("units") and now - idx.get("rebalanced_at", 0) < ICFG["rebalance_hours"] * 3600:
        return idx
    prices = prices or {m: c["price_usd"] for m, c in cands.items() if c.get("price_usd")}
    level = (level_from_prices(idx, prices) if idx.get("units") else None) or idx.get("level") or ICFG["base_level"]
    weights = select_components(cands)
    if not weights:
        return idx
    units = {m: level * w / prices[m] for m, w in weights.items() if prices.get(m)}
    idx = {
        "level": level,
        "units": units,
        "weights": weights,
        "last_prices": {m: prices[m] for m in units},
        "symbols": {m: cands[m]["symbol"] for m in units if m in cands},
        "rebalanced_at": now,
    }
    state.save("index", idx)
    state.log_event("index", f"GRAD rebalanced: {len(units)} coins, level {level:.2f}")
    return idx


def drop_component(mint: str, reason: str) -> None:
    """Emergency removal (rug): the coin's weight moves to the rest at the current level."""
    idx = state.load("index")
    if mint not in idx.get("units", {}):
        return
    level = level_from_prices(idx, idx.get("last_prices", {})) or idx["level"]
    weights = {m: w for m, w in idx.get("weights", {}).items() if m != mint and m in idx["units"]}
    total = sum(weights.values()) or 1
    prices = idx["last_prices"]
    idx["units"] = {m: level * (w / total) / prices[m] for m, w in weights.items() if prices.get(m)}
    idx["weights"] = {m: weights[m] / total for m in idx["units"]}
    idx["level"] = level
    state.save("index", idx)
    state.log_event("index", f"Removed from GRAD: {idx.get('symbols', {}).get(mint, mint)} ({reason})")
