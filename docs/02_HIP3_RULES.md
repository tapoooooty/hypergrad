# HIP-3 rules that shape HyperGrad

This is a summary of the official Hyperliquid documentation as of October 29, 2026. Parameters change, so re-check them before deploying.

## Deployer

- **Stake 500,000 HYPE** on mainnet, held for at least **183 days** after the DEX is deployed. The requirement is expected to fall over time.
- One deployer runs one perp DEX, with its own order books, margin and settings.
- The DEX code is 2 to 4 lowercase letters (`grad`). Assets are named `grad:TICKER`.
- Any permitted quote asset can be collateral; HyperGrad uses USDC.

## Listing

- **The first 3 assets skip the auction.**
- Further assets go through a **Dutch auction shared by all DEXs** (HIP-1 parameters, 500 HYPE minimum).
- Reserve deployments: `7 + 0.2 × n_auction_deployments` at the current auction price, without waiting for the timer.
- `haltTrading` stops a market and settles every position at the current mark price. The same action resumes it.

## Oracle (the deployer's job)

- Prices are set with `setOracle`, at least **2.5 s** apart. Every **3 s** is recommended.
- After **10 s** without updates, the mark price falls back to the local mark.
- **Mark moves are clamped to 1% per update.** This matters for memecoins: in an 80% crash the mark lags by up to about 20% per minute.
- All prices are clamped to **10x the start-of-day value**.
- The docs warn that most price indices make poor perp oracles. The deployer can be slashed for any market on its DEX.

## Margin and caps

- Margin tables have up to 3 tiers, with leverage from 1x to 50x.
- **The open interest cap cannot be set below $1,000,000**, or half of the current open interest if that is higher.
- **Cross margin is forbidden for assets expected to move 50% in a day more than once a month.** That covers every memecoin, so HyperGrad lists `strictIsolated` only. Enabling cross margin is irreversible and slashable.

## Fees

- On a standard HIP-3 market, traders pay **2x** Hyperliquid's base rate (taker 0.09% vs 0.045%). The deployer and the protocol split it evenly.
- The deployer can add an extra 0 to 300% share. Above 100%, the protocol's share rises to match.
- **Growth mode** cuts all-in fees by ≥ 90% (taker ~0.009%), and the deployer's share falls about tenfold with it. On October 29, 2026, 155 of 167 live HIP-3 markets had growth mode on.
- Fee settings can change once every 30 days.

## Slashing

- Validators decide by stake-weighted vote.
- Guidelines: up to **100%** for invalid state transitions or long network downtime, up to **50%** for brief downtime, up to **20%** for performance degradation.
- Slashing does not distinguish malice from incompetence. A compromised key counts.
- Slashed HYPE is burned, not paid to affected traders.
- Stake stays slashable during the 7-day unstaking queue.

## HIP-3* (testnet only)

- Optional permissioned markets with an onchain wallet allowlist managed by the deployer.
- Kraken's parent Payward plans to be the first CFTC-regulated deployer. ICE and trade.xyz are building a regulated venue on Hyperliquid's rails.
- Useful for HyperGrad if KYC or geo-restrictions are needed.

## Sources

- [HIP-3: Builder-deployed perpetuals](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals)
- [HIP-3 deployer actions](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/hip-3-deployer-actions)
- [Fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)
- [Growth mode markets, live list](https://hyperliquidguide.com/guides/trading/hyperliquid-growth-mode-markets)
- [HIP-3* announcement](https://x.com/HyperliquidX/status/2114772826435866711)
