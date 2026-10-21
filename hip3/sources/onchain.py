"""Direct on-chain prices from PumpSwap pools.

A PumpSwap pool owns two token accounts: the coin vault and the quote vault (wrapped SOL
or USDC). Price = quote reserve / coin reserve, converted to USD with the SOL price.
This reads the chain itself, so it keeps working when DexScreener or Jupiter are down.

It costs two RPC calls per pool per oracle tick. Use a private RPC (Helius, QuickNode,
Triton) when this source is enabled.
"""
from .solana_rpc import SolanaRPC

WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qFxEPM5ZQKoVZLnLUqHbUsqv2c"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"


def _balance(rpc: SolanaRPC, owner: str, mint: str) -> float:
    r = rpc.call("getTokenAccountsByOwner", [owner, {"mint": mint}, {"encoding": "jsonParsed", "commitment": "confirmed"}])
    total = 0.0
    for acc in r.get("value", []):
        total += float(acc["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0)
    return total


def pool_price_usd(rpc: SolanaRPC, pool: str, coin_mint: str, quote_mint: str, sol_usd: float | None) -> tuple[float, float] | None:
    """(price_usd, liquidity_usd) for one constant-product pool, or None."""
    coin = _balance(rpc, pool, coin_mint)
    quote = _balance(rpc, pool, quote_mint)
    if coin <= 0 or quote <= 0:
        return None
    if quote_mint == WSOL:
        if not sol_usd:
            return None
        quote_usd = quote * sol_usd
    elif quote_mint in (USDC, USDT):
        quote_usd = quote
    else:
        return None
    return quote_usd / coin, 2 * quote_usd


def pumpswap_pools(pairs: list[dict]) -> list[tuple[str, str]]:
    """(pool address, quote mint) for every PumpSwap pair DexScreener knows about."""
    out = []
    for p in pairs:
        if p.get("dexId") != "pumpswap" or not p.get("pairAddress"):
            continue
        quote = (p.get("quoteToken") or {}).get("address")
        if quote in (WSOL, USDC, USDT):
            out.append((p["pairAddress"], quote))
    return out
