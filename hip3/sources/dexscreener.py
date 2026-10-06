"""DexScreener API (public, no key).

Rate limits: /tokens/v1 allows 300 req/min, /token-profiles and /token-boosts allow 60 req/min.
"""
from ..http import get_json

BASE = "https://api.dexscreener.com"


def pairs_for_tokens(mints: list[str]) -> dict[str, list[dict]]:
    """All Solana pools for a list of tokens. Returns {mint: [pair, ...]}."""
    out: dict[str, list[dict]] = {m: [] for m in mints}
    for i in range(0, len(mints), 30):
        chunk = mints[i : i + 30]
        data = get_json(f"{BASE}/tokens/v1/solana/{','.join(chunk)}")
        if not isinstance(data, list):
            continue
        for pair in data:
            if pair.get("chainId") != "solana":
                continue
            base = (pair.get("baseToken") or {}).get("address")
            if base in out:
                out[base].append(pair)
    return out


def discover_mints() -> set[str]:
    """Fresh and boosted Solana tokens from DexScreener feeds."""
    mints: set[str] = set()
    for path in ("/token-profiles/latest/v1", "/token-boosts/latest/v1", "/token-boosts/top/v1"):
        try:
            data = get_json(BASE + path)
        except RuntimeError:
            continue
        for item in data if isinstance(data, list) else []:
            if item.get("chainId") == "solana" and item.get("tokenAddress"):
                mints.add(item["tokenAddress"])
    for q in ("pumpswap", "pump.fun"):
        try:
            data = get_json(f"{BASE}/latest/dex/search", params={"q": q})
        except RuntimeError:
            continue
        for pair in data.get("pairs") or []:
            if pair.get("chainId") == "solana":
                addr = (pair.get("baseToken") or {}).get("address")
                if addr:
                    mints.add(addr)
    return mints


def summarize(pairs: list[dict]) -> dict | None:
    """Aggregated token metrics across all of its pools."""
    good = [p for p in pairs if p.get("priceUsd")]
    if not good:
        return None
    best = max(good, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
    liq = sum((p.get("liquidity") or {}).get("usd") or 0 for p in good)
    vol = sum((p.get("volume") or {}).get("h24") or 0 for p in good)
    created = [p.get("pairCreatedAt") for p in good if p.get("pairCreatedAt")]
    base = best.get("baseToken") or {}
    return {
        "mint": base.get("address"),
        "symbol": base.get("symbol") or "",
        "name": base.get("name") or "",
        "price_usd": float(best["priceUsd"]),
        "mcap_usd": float(best.get("marketCap") or best.get("fdv") or 0),
        "liquidity_usd": float(liq),
        "volume_24h_usd": float(vol),
        "price_change_1h_pct": float((best.get("priceChange") or {}).get("h1") or 0),
        "first_pair_ms": min(created) if created else None,
        "best_pair": best.get("pairAddress"),
        "dex_ids": sorted({p.get("dexId") for p in good if p.get("dexId")}),
        "url": best.get("url"),
    }


def price_quotes(pairs: list[dict]) -> list[tuple[float, float]]:
    """(price, liquidity) per pool, used by the oracle."""
    quotes = []
    for p in pairs:
        try:
            px = float(p.get("priceUsd") or 0)
        except (TypeError, ValueError):
            continue
        liq = float((p.get("liquidity") or {}).get("usd") or 0)
        if px > 0 and liq > 0:
            quotes.append((px, liq))
    return quotes
