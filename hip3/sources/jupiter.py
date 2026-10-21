"""Jupiter Price API v3: aggregated USD price across Solana DEX routes.

Docs: https://dev.jup.ag/docs/price-api/v3
"""
from ..config import env
from ..http import get_json

SOL_MINT = "So11111111111111111111111111111111111111112"


def _base() -> str:
    # An API key from portal.jup.ag raises rate limits; without one the lite endpoint is used.
    return "https://api.jup.ag/price/v3" if env("JUPITER_API_KEY") else "https://lite-api.jup.ag/price/v3"


def prices(mints: list[str]) -> dict[str, float]:
    """{mint: usd_price}. Mints without a reliable price are omitted."""
    out: dict[str, float] = {}
    headers_key = env("JUPITER_API_KEY")
    for i in range(0, len(mints), 50):
        chunk = mints[i : i + 50]
        params = {"ids": ",".join(chunk)}
        if headers_key:
            params["apiKey"] = headers_key
        data = get_json(_base(), params=params, retries=2)
        if not isinstance(data, dict):
            continue
        body = data.get("data", data)
        for mint, item in body.items():
            if not isinstance(item, dict):
                continue
            px = item.get("usdPrice", item.get("price"))
            try:
                px = float(px)
            except (TypeError, ValueError):
                continue
            if px > 0:
                out[mint] = px
    return out
