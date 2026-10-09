"""Pricing: robust spot price, multipliers for tiny prices, Hyperliquid price formatting."""
import math
import re

# Memecoins trade at $0.00001. Hyperliquid accepts at most 5 significant figures and
# (6 - szDecimals) decimals, so we list "bundles": MWIF = 1,000,000 WIF (like kPEPE on Hyperliquid).
MULTIPLIERS = [(1, ""), (1_000, "K"), (1_000_000, "M"), (1_000_000_000, "B"), (1_000_000_000_000, "T")]


def choose_multiplier(price_usd: float) -> tuple[int, str]:
    """Multiplier that puts the bundle price into [1, 1000)."""
    for mult, prefix in MULTIPLIERS:
        if price_usd * mult >= 1:
            return mult, prefix
    return MULTIPLIERS[-1]


def sz_decimals_for(px: float) -> int:
    """szDecimals so that the minimum size step is worth about $1 to $10."""
    if px <= 0:
        return 0
    return max(0, min(5, math.ceil(math.log10(px)) - 1))


def sanitize_ticker(symbol: str, prefix: str, taken: set[str]) -> str:
    base = re.sub(r"[^A-Z0-9]", "", symbol.upper())[:6] or "MEME"
    name = f"{prefix}{base}"
    i = 2
    while name in taken:
        name = f"{prefix}{base[:5]}{i}"
        i += 1
    return name


def format_px(px: float, sz_decimals: int) -> str:
    """Perp price string: ≤5 significant figures and ≤(6 - szDecimals) decimals."""
    if px <= 0:
        raise ValueError("price must be positive")
    max_dec = max(0, 6 - sz_decimals)
    digits = 5 - int(math.floor(math.log10(abs(px)))) - 1
    if digits <= 0:
        return str(int(round(px, digits)))
    dec = max(0, min(max_dec, digits))
    s = f"{round(px, dec):.{dec}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def weighted_median(quotes: list[tuple[float, float]]) -> float | None:
    """Liquidity-weighted median price across pools."""
    if not quotes:
        return None
    qs = sorted(quotes, key=lambda q: q[0])
    total = sum(w for _, w in qs)
    acc = 0.0
    for px, w in qs:
        acc += w
        if acc >= total / 2:
            return px
    return qs[-1][0]


def source_deviation_pct(quotes: list[tuple[float, float]], ref: float) -> float:
    """Max deviation of significant pools (≥10% of liquidity) from the reference price."""
    if not quotes or ref <= 0:
        return 0.0
    total = sum(w for _, w in quotes)
    devs = [abs(px / ref - 1) * 100 for px, w in quotes if w >= 0.1 * total]
    return max(devs) if devs else 0.0


def ema(prev: float | None, new: float, alpha: float) -> float:
    return new if prev is None else prev + alpha * (new - prev)
