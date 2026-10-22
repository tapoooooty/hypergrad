"""Oracle backtest: how far would the protocol mark have lagged a coin's real price?

python -m hip3 backtest <mint>

Pulls 1-minute candles for the coin's largest pool from GeckoTerminal, then replays them
through HIP-3's mark rule: at most 1% per update, one update every 3 seconds. Reports the
worst lag and how long the mark trailed the real price. Large lags mean liquidations would
fire late on that coin, which is the main argument for low leverage and the index.
"""
from .config import CFG
from .http import get_json
from .sources import dexscreener

GT = "https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/{tf}"
UPDATES_PER_MIN = 20  # one setOracle every 3 s
STEP = 0.01           # protocol clamp per update


def candles(pool: str) -> list[list[float]]:
    tf = CFG.get("backtest", {}).get("timeframe", "minute")
    data = get_json(GT.format(pool=pool, tf=tf), params={"aggregate": 1, "limit": CFG.get("backtest", {}).get("limit", 1000)})
    rows = data["data"]["attributes"]["ohlcv_list"]
    return sorted(rows, key=lambda r: r[0])


def replay(rows: list[list[float]]) -> dict:
    mark = rows[0][4]
    worst = (0.0, 0)
    lag5 = lag20 = 0
    alerts = 0
    prev_close = rows[0][4]
    for ts, o, h, l, c, v in rows[1:]:
        target = c
        for _ in range(UPDATES_PER_MIN):
            if mark <= 0:
                break
            ratio = target / mark
            mark *= max(1 - STEP, min(1 + STEP, ratio))
        lag = mark / target - 1
        if abs(lag) > abs(worst[0]):
            worst = (lag, int(ts))
        lag5 += abs(lag) > 0.05
        lag20 += abs(lag) > 0.20
        if prev_close and abs(c / prev_close - 1) > CFG["oracle"]["alert_move_pct_per_min"] / 100:
            alerts += 1
        prev_close = c
    return {"minutes": len(rows), "worst_lag": worst[0], "worst_ts": worst[1], "lag5": lag5, "lag20": lag20, "alerts": alerts}


def run(mint: str) -> None:
    import time

    pairs = dexscreener.pairs_for_tokens([mint]).get(mint, [])
    if not pairs:
        raise SystemExit("No Solana pools found for this mint on DexScreener")
    best = max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
    rows = candles(best["pairAddress"])
    if len(rows) < 10:
        raise SystemExit("Not enough candle history for this pool")
    r = replay(rows)
    sym = (best.get("baseToken") or {}).get("symbol", mint[:6])
    when = time.strftime("%Y-%m-%d %H:%M", time.gmtime(r["worst_ts"])) if r["worst_ts"] else "n/a"
    print(f"{sym}: {r['minutes']} one-minute candles from pool {best['pairAddress']} ({best.get('dexId')})")
    print(f"Worst mark lag:            {r['worst_lag']:+.1%} at {when} UTC")
    print(f"Minutes lagging over 5%:   {r['lag5']}")
    print(f"Minutes lagging over 20%:  {r['lag20']}")
    print(f"Minutes that would alert:  {r['alerts']} (move over {CFG['oracle']['alert_move_pct_per_min']:.0f}% in a minute)")
    lev = CFG["tiers"]["tier1"]["max_leverage"]
    if abs(r["worst_lag"]) > 0.5 / lev:
        print(f"Verdict: at {lev}x a position could sit past its liquidation price on a stale mark. Keep this coin in the index only.")
    else:
        print(f"Verdict: mark lag stayed inside the {lev}x liquidation buffer in this window.")
