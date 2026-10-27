# Roadmap and risks

## Roadmap

- [x] Scanner, tiers, GRAD index, listing and halting, oracle daemon
- [x] Manager with automatic delisting and an oracle watchdog
- [x] Dashboard
- [x] Telegram alerts and heartbeat
- [x] Preflight `doctor`
- [x] Market maker with inventory skew and volatility-based spreads
- [x] Multi-source oracle (DexScreener, Jupiter, on-chain PumpSwap) with a standby failover
- [x] Funding settings, oracle backtest
- [x] Docker, docker-compose, systemd units, VPS setup script, CI
- [ ] **Testnet season.** Run the manager for a week, `init-dex` on testnet, keep the oracle up around the clock, trade it, tune thresholds.
- [ ] **Oracle on a VPS.** Rent a Tokyo server and a second one elsewhere for the standby ([06_OPERATIONS.md](06_OPERATIONS.md)).
- [ ] **Stake.** Apply to Kinetiq Launch for a crowdfunded 500k HYPE stake, or partner with a staker. Publish the oracle methodology and this listing policy.
- [ ] **Mainnet phase 1.** GRAD plus two single perps (the three free slots), 2x, $1M OI cap.
- [ ] **Trading front end with a builder code.** Extra fee income and our own brand; the graduates feed already exists.
- [ ] **Phase 2.** More slots through the auction, tier 2 at 3x, themed indices (cats, AI, HYPE-paired coins).

## Risks

| Risk | What handles it |
|---|---|
| Pool manipulation to trigger liquidations | Single perps need $500K held 24 h, $100K liquidity and 2x max leverage; thinner coins trade only inside the index at ≤ 10% |
| A rug (−90% in seconds) | Low leverage, isolated margin, index removal on liquidity collapse, auto-halt |
| Bad DexScreener data | Price frozen when sources disagree by > 15% or go missing; halt after 120 s |
| Oracle downtime leading to slashing | Auto-restart scripts, watchdog alerts on Telegram, VPS deployment |
| Compromised deployer key | Separate oracle key through `oracleUpdater`; the deployer key is used only for rare actions |
| Regulation | Geo-restrictions on the front end, HIP-3* allowlists once live, legal counsel |
