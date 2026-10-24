import time

from hip3.scanner import classify


def coin(**kw):
    now = int(time.time())
    base = dict(mint="abcpump", mcap_usd=6e6, liquidity_usd=600e3, volume_24h_usd=2e6,
                price_change_1h_pct=2, created_ms=(now - 100 * 3600) * 1000,
                history=[[now - h * 3600, 6e6, 600e3] for h in range(30, -1, -1)])
    base.update(kw)
    return base


def test_tier1_coin():
    tier, _ = classify(coin(), int(time.time()))
    assert tier == "tier1"


def test_pump_blocks_listing():
    tier, why = classify(coin(price_change_1h_pct=500), int(time.time()))
    assert tier is None and "pumping" in why[0]


def test_non_pump_coin_rejected():
    tier, _ = classify(coin(mint="abc"), int(time.time()))
    assert tier is None
