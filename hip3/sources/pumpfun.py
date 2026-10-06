"""Unofficial pump.fun frontend API: graduated coins sorted by market cap.

If the API is unavailable or changes, the scanner keeps working on DexScreener alone.
"""
from ..http import get_json

BASE = "https://frontend-api-v3.pump.fun"


def graduated_coins(pages: int = 4, page_size: int = 50) -> list[dict]:
    coins: list[dict] = []
    for page in range(pages):
        try:
            data = get_json(
                f"{BASE}/coins",
                params={
                    "offset": page * page_size,
                    "limit": page_size,
                    "sort": "market_cap",
                    "order": "DESC",
                    "includeNsfw": "false",
                    "complete": "true",
                },
            )
        except RuntimeError:
            break
        items = data if isinstance(data, list) else data.get("coins", []) if isinstance(data, dict) else []
        if not items:
            break
        for c in items:
            mint = c.get("mint")
            if not mint:
                continue
            coins.append(
                {
                    "mint": mint,
                    "symbol": c.get("symbol") or "",
                    "name": c.get("name") or "",
                    "creator": c.get("creator"),
                    "created_ms": c.get("created_timestamp"),
                    "complete": bool(c.get("complete")),
                    "usd_market_cap": c.get("usd_market_cap"),
                }
            )
    return coins
