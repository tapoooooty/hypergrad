"""HIP-3 deployer return calculator.

Hyperliquid base-tier fees: taker 0.045%, maker 0.015%.
On HIP-3 with scale = 1 traders pay 2x and the deployer earns 1x the base rate.
Growth mode: everything × ~0.1.
Run: python -m hip3 economics   (or python economics/model.py)
"""
HYPE_PRICE = 90.0          # USD per HYPE; adjust to the market
STAKE_HYPE = 500_000
STAKING_APR = 0.023        # base HYPE staking yield
BASE_TAKER = 0.00045
BASE_MAKER = 0.00015
DISCOUNTS = 0.15           # trader referral and staking discounts
OPEX_PER_MONTH = 25_000    # servers, oracle, marketing, market-maker incentives

SCENARIOS = {
    "Weak": 3_000_000,
    "Base": 20_000_000,
    "Strong": 75_000_000,
    "Meta mania": 250_000_000,
}


def deployer_fee_rate(scale: float = 1.0, growth_mode: bool = False) -> float:
    """Deployer revenue per $1 of volume (taker + maker side of one trade)."""
    rate = (BASE_TAKER + BASE_MAKER) * scale * (1 - DISCOUNTS)
    return rate * (0.1 if growth_mode else 1.0)


def main() -> None:
    stake_usd = STAKE_HYPE * HYPE_PRICE
    print(f"Stake: {STAKE_HYPE:,} HYPE × ${HYPE_PRICE} = ${stake_usd:,.0f}")
    print(f"Staking alone: ${stake_usd * STAKING_APR:,.0f}/yr ({STAKING_APR:.1%})\n")
    for gm in (False, True):
        print(f"--- growth mode {'ON' if gm else 'OFF'} (scale 1.0) ---")
        print(f"{'Scenario':<12}{'Volume/day':>14}{'Rev/day':>12}{'Rev/yr':>15}{'Net/yr':>15}{'Stake ROI':>11}")
        for name, vol in SCENARIOS.items():
            day = vol * deployer_fee_rate(1.0, gm)
            year = day * 365
            net = year - OPEX_PER_MONTH * 12 + stake_usd * STAKING_APR
            print(f"{name:<12}{vol:>14,.0f}{day:>12,.0f}{year:>15,.0f}{net:>15,.0f}{net / stake_usd:>11.1%}")
        print()
    be = OPEX_PER_MONTH * 12 / 365 / deployer_fee_rate()
    print(f"Opex break-even (growth mode off): ~${be:,.0f} of daily volume")
    print("Reference: in early June 2026 all of HIP-3 did ~$4.8B per week, ~95% of it on trade.xyz.")


if __name__ == "__main__":
    main()
