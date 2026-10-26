# Concept

HyperGrad is a builder-deployed perp DEX on Hyperliquid (HIP-3), the same mechanism trade.xyz uses. On October 29, 2026, ICE, the owner of the NYSE, signed an agreement with trade.xyz. HyperGrad's niche is Solana memecoins that graduate from pump.fun.

A coin that holds a $500K market cap joins the **GRAD index perp**. A coin that keeps that cap for a day, with real liquidity behind it, gets **its own perp**. Traders can go long or short with leverage on Hyperliquid's order book, which spot-only memecoin trading never allowed.

## Why this can work

- **There is room.** HIP-3 today is almost entirely TradFi: stocks, oil, gold, indices. trade.xyz carries ~95% of HIP-3 volume, and no deployer focuses on young memecoins.
- **Shorting Solana memes is hard.** Spot only goes one way. Perps add shorts and leverage, which is what the pump.fun crowd already wants.
- **pump.fun is already sending users to Hyperliquid.** It added HyperEVM trading in August 2026 and Hyperliquid-powered perps on October 28, 2026. HyperGrad sits on that bridge.
- **No exchange to build.** HIP-3 provides matching, margin, liquidations and the API. HyperGrad provides the market list, the oracle, risk settings and the front end.

## The hard problem, and the answer

A $500K market cap is very small for a perp. Hyperliquid will not let a deployer set an open interest cap below **$1M** per asset, so open interest could exceed the coin's entire market cap. That invites manipulation: push the spot pool, liquidate the other side, exit. In March 2025 the JELLY squeeze on Hyperliquid itself showed how this goes. A deployer whose oracle is gamed can be slashed by up to 100% of its stake.

So $500K is the entry to the funnel, not an automatic single listing:

| Tier | Condition (summary) | What the coin gets |
|---|---|---|
| Tier 0, graduate | pump.fun coin, $500K held for 6 h, basic safety filters | A weight in the GRAD index perp |
| Tier 1, own perp | $500K held 24 h, $100K pool liquidity, 48 h old | Its own perp, 2x isolated, OI cap $1M |
| Tier 2, blue chip | $5M market cap, $500K liquidity | Up to 3x, OI cap $2M |

The GRAD index is the core idea:

- **Slots.** One market instead of a hundred. The first three HIP-3 assets are free; the rest go through a Dutch auction starting at 500 HYPE.
- **One trade for the whole meta.** "Short this week's graduates" becomes a single trade.
- **Built-in protection.** No component can exceed 10% of the index, so one manipulated coin cannot move it much.

Full rules are in [03_LISTING_POLICY.md](03_LISTING_POLICY.md).

## Money

- **Stake: 500,000 HYPE**, about **$45M** at ~$90 per HYPE. It is locked for at least 183 days and is slashable.
- The realistic way to raise it is a crowdfunded stake through **Kinetiq Launch**. Markets by Kinetiq and Borsa launched this way, and stakers receive a share of fees.
- Deployer revenue is a share of trading fees. Scenarios are in [04_ECONOMICS.md](04_ECONOMICS.md).
