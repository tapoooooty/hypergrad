<p align="center">
  <img src="docs/assets/logo.png" alt="HyperGrad logo" width="96">
</p>

<p align="center">
  <img src="docs/assets/banner.png" alt="HyperGrad: perps for the memecoins that made it" width="100%">
</p>

<p align="center">
  <a href="https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals"><img alt="Hyperliquid HIP-3" src="https://img.shields.io/badge/Hyperliquid-HIP--3-97FCE4?labelColor=0B2420"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-97FCE4?labelColor=0B2420">
  <img alt="Docker" src="https://img.shields.io/badge/docker-compose-97FCE4?labelColor=0B2420">
  <img alt="Status: testnet" src="https://img.shields.io/badge/status-testnet-F2B544?labelColor=0B2420">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-97FCE4?labelColor=0B2420"></a>
</p>

**HyperGrad** is a builder-deployed perpetuals DEX on [Hyperliquid](https://hyperliquid.xyz) for Solana memecoins that graduate from [pump.fun](https://pump.fun).

- A coin that holds a **$500K** market cap joins **`grad:GRAD`**, an index perp of graduates.
- A coin that holds **$500K** for a full day, with real liquidity behind it, also gets **its own perp**, such as `grad:MWIF` (2x).
- Past **$5M** it becomes a blue chip with leverage up to 3x.
- An oracle prices every market from three independent Solana sources every 3 seconds, with a standby oracle on a second server.
- A market maker keeps both sides of every book quoted.
- A manager scans, rebalances and retires markets on its own.
- A dashboard, Telegram alerts and a preflight `doctor` keep you informed.

<p align="center">
  <img src="docs/assets/dashboard.png" alt="HyperGrad dashboard" width="100%">
  <br><sub>The dashboard, shown here with demo data.</sub>
</p>

## Contents

- [Why HyperGrad](#why-hypergrad)
- [How it works](#how-it-works)
- [Quick start](#quick-start)
- [Preflight: doctor](#preflight-doctor)
- [Market maker](#market-maker)
- [Oracle sources and failover](#oracle-sources-and-failover)
- [Running on a server](#running-on-a-server)
- [Telegram alerts](#telegram-alerts)
- [Commands](#commands)
- [Configuration](#configuration)
- [What code cannot do](#what-code-cannot-do)
- [Project layout](#project-layout)
- [Risks and limits](#risks-and-limits)
- [Documentation](#documentation)
- [Links](#links)

## Why HyperGrad

[HIP-3](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals) lets anyone who stakes 500,000 HYPE run their own perp DEX on Hyperliquid's matching engine. The deployer brings the markets and the oracle; Hyperliquid handles order books, margin and liquidations. trade.xyz used this to build stock and commodity perps, and on October 29, 2026 ICE, the owner of the NYSE, signed with it to bring those markets to the US.

Memecoins are the obvious gap. On Solana you can only buy them. HyperGrad lets traders short them and use leverage, and it starts with an index so that a single thin coin cannot be turned against the market.

## How it works

<p align="center"><img src="docs/assets/architecture.png" alt="Architecture" width="100%"></p>

| Process | What it does |
|---|---|
| **Manager** | Every 10 minutes: pulls graduated coins from pump.fun and DexScreener, checks holders over Solana RPC, assigns tiers, rebalances GRAD daily, halts markets that fall below their tier, flags coins ready for their own perp, and watches the oracle. |
| **Oracle** | Every ~3 seconds: one price per source, median across sources, EMA for the mark, one `setOracle` for every live market. Freezes on bad data, halts a market that stays frozen. |
| **Market maker** | Post-only bid and ask ladders around the oracle price, skewed against its own position, widened when volatility rises, pulled when a market halts or the oracle freezes. |
| **Dashboard** | Read-only view of everything above, plus `/api/health` for the standby oracle. |

### From graduate to blue chip

<p align="center"><img src="docs/assets/tiers.png" alt="Tiers" width="100%"></p>

A coin gets its own perp at the same **$500K** that brings it into the index, but only once it has held that cap for 24 hours, has at least **$100K** of pool liquidity and $500K of daily volume, and is two days old. Leverage on these young markets is capped at **2x**. Hyperliquid will not accept an open interest cap below **$1M**, so a small pool can still be pushed against perp traders; the hold time, the liquidity floor, low leverage and the oracle freeze are there to make that expensive. The full policy is in [docs/03_LISTING_POLICY.md](docs/03_LISTING_POLICY.md).

### The oracle

<p align="center"><img src="docs/assets/oracle.png" alt="Oracle pipeline" width="100%"></p>

Memecoins trade at fractions of a cent and Hyperliquid prices allow five significant figures, so HyperGrad lists bundles the way Hyperliquid lists `kPEPE`: `MWIF` is one million WIF. The bundle size is picked when a coin is listed.

<p align="center"><img src="docs/assets/term-oracle.png" alt="Oracle log" width="88%"></p>

## Quick start

You need Python 3.10 or newer and a Hyperliquid wallet. Everything defaults to testnet.

### Windows

1. Run **`setup.bat`**. It creates `.venv`, installs dependencies and copies `.env.example` to `.env`.
2. Fill in **`.env`**: deployer key, oracle key, market maker key, Telegram.
3. Run **`doctor.bat`** and fix anything marked FAIL.
4. Run **`scan.bat`**, then leave **`start_manager.bat`** running. Coins need about 6 hours of history to reach tier 0.
5. Open the dashboard with **`start_dashboard.bat`**.
6. When the index has coins, create the DEX:
   ```powershell
   .venv\Scripts\activate
   python -m hip3 init-dex
   ```
7. Start **`start_oracle.bat`** and keep it running while any market is live.
8. Set `market_maker.enabled` to `true` and start **`start_mm.bat`**.
9. List single perps as candidates appear: `python -m hip3 list <mint>`.

### macOS and Linux

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then fill it in
python -m hip3 doctor
python -m hip3 scan
python -m hip3 manager &        # leave running
python -m hip3 serve            # http://localhost:8787
python -m hip3 init-dex         # once the index has coins
python -m hip3 oracle &         # keep running
python -m hip3 mm               # after enabling it in config.json
```

<p align="center"><img src="docs/assets/term-scan.png" alt="Scanner output" width="88%"></p>

## Preflight: doctor

`python -m hip3 doctor` runs every check it can without sending a transaction. Run it before `init-dex` and after every change to `.env` or `config.json`.

| Area | What it checks |
|---|---|
| Environment | Python version, installed packages, `.env` present |
| Config | DEX code format, tier order, OI caps above the protocol minimum, leverage range, oracle interval |
| Hyperliquid | API reachable and latency, whether the DEX name is free or yours, slot auction price |
| Keys and stake | Deployer address, staked HYPE against the 500k requirement, spot HYPE and USDC, oracle updater matches config, market maker uses a separate account |
| Sources | DexScreener, pump.fun, Solana RPC health (and whether it is the slow public one), Jupiter |
| Alerts | Telegram bot token and chat id |
| State | Candidates, index size, how long ago the oracle last pushed |

It exits with code 1 if anything failed, so it can gate a deploy script.

## Market maker

An empty order book is a dead market. `python -m hip3 mm` keeps a ladder on both sides of every market in `market_maker.markets`.

| Behaviour | Setting |
|---|---|
| Levels per side and their spacing | `levels`, `level_spacing_bps` |
| Base spread, widened by one-minute volatility | `base_spread_bps`, `vol_spread_mult` |
| Size per order | `order_size_usd` |
| Position limit: no new bids above it, no new asks below minus it | `max_position_usd` |
| Ladder shift against the position at the limit | `skew_bps_at_max` |
| Requote when fair moves this much, or after this long | `requote_bps`, `requote_sec` |

Orders are ALO (add liquidity only), so the bot never takes and never pays taker fees. It pulls every quote when a market is halted, when the oracle freezes or goes stale, and when you stop it with Ctrl+C. `python -m hip3 mm --dry-run` prints the ladder without trading, and `python -m hip3 mm-cancel` pulls everything.

Fund a **separate account** with USDC and put its key in `HL_MM_PRIVATE_KEY`. The deployer key should never trade.

## Oracle sources and failover

Each source gets one vote; the spot price is their median.

| Source | What it reads | Setting |
|---|---|---|
| `dexscreener` | Every Solana pool for the coin, liquidity-weighted median | on by default |
| `jupiter` | [Jupiter Price API v3](https://dev.jup.ag/docs/price-api/v3), aggregated across routes | on by default; `JUPITER_API_KEY` raises limits |
| `onchain` | Reserves of the coin's largest PumpSwap pool, read over Solana RPC | needs a private RPC |

`oracle.min_sources` sets how many must answer before a price moves. With all three on, set it to 2, so a single broken feed freezes a price instead of moving it.

**Standby oracle.** Run a second copy on another server with `oracle.standby_primary_url` set to the primary's dashboard (reach it over an SSH tunnel or a private network). The standby computes every tick and only sends while the primary's `/api/health` reports no push in the last `failover_after_sec`. Allow its key once:

```bash
python -m hip3 add-oracle-signer 0xSTANDBY_ADDRESS
```

**Funding.** `funding.multiplier` and `funding.clamp_8h` are applied at listing. Run `python -m hip3 apply-funding` after changing them.

**Backtest.** Before giving a coin its own perp:

```bash
python -m hip3 backtest <mint>
```

It replays the coin's one-minute history from [GeckoTerminal](https://www.geckoterminal.com/) through HIP-3's mark rule (1% per update, one update every 3 s) and reports how far and how long the mark would have trailed the real price.

## Running on a server

The oracle cannot sleep, so production runs on a VPS. Docker is the shortest path:

```bash
scp -r ./HIP-3/* root@SERVER:/opt/hypergrad/
ssh root@SERVER 'bash /opt/hypergrad/deploy/vps-setup.sh'      # Docker, firewall, NTP, updates
ssh root@SERVER 'nano /opt/hypergrad/.env'
ssh root@SERVER 'cd /opt/hypergrad && docker compose run --rm oracle doctor'
ssh root@SERVER 'cd /opt/hypergrad && docker compose up -d'    # oracle, manager, dashboard
ssh root@SERVER 'cd /opt/hypergrad && docker compose --profile mm up -d'   # plus the market maker
ssh -L 8787:localhost:8787 root@SERVER                         # dashboard on your machine
```

| File | Purpose |
|---|---|
| [`Dockerfile`](Dockerfile) | Python 3.12 slim image, non-root user |
| [`docker-compose.yml`](docker-compose.yml) | `oracle`, `manager`, `dashboard`, and `mm` behind a profile; restart unless stopped; state on a volume; rotated logs |
| [`deploy/vps-setup.sh`](deploy/vps-setup.sh) | Fresh Ubuntu: Docker, SSH-only firewall, time sync, unattended upgrades, `.env` permissions |
| [`deploy/systemd/`](deploy/systemd) | Unit files if you prefer a virtualenv to Docker |

The dashboard binds to localhost inside the server on purpose. Reach it through an SSH tunnel rather than opening a port.

Where to rent a server, which Solana RPC to pick and how to lay out primary and standby are in [docs/06_OPERATIONS.md](docs/06_OPERATIONS.md#3-servers).

## Telegram alerts

<img src="docs/assets/telegram.png" alt="Telegram alerts" width="380" align="right">

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy its token into `TELEGRAM_BOT_TOKEN`.
2. Send the bot any message, or add it to a group.
3. Run `python -m hip3 tg-chatid` and copy the id into `TELEGRAM_CHAT_ID`. Separate several ids with commas.
4. Run `telegram_test.bat` to confirm delivery.

| Alert | When |
|---|---|
| ⚠️ Alert | A price freezes, or moves more than 40% in a minute |
| ⛔ Halt | A market is halted and settled |
| 🐕 Watchdog | The oracle has not pushed for 30 s, the standby takes over, or either recovers |
| 🎯 Candidate | A coin qualifies for its own perp |
| 🚀 Listing | A market is listed or resumed |
| 💱 Mm | The market maker starts, pulls quotes or gets orders rejected |
| 🔥 Error | An oracle tick, manager cycle or market maker tick fails |
| 💚 Heartbeat | Every 12 h: live markets and their prices |

Identical alerts are suppressed for 5 minutes and sending never blocks the oracle. Choose the alert types with `telegram.kinds` in config.json.

<br clear="right">

## Commands

| Command | What it does |
|---|---|
| `python -m hip3 doctor` | Preflight checks |
| `python -m hip3 scan` | Find graduates, compute metrics and tiers |
| `python -m hip3 index [--force]` | Show or recompute the GRAD composition |
| `python -m hip3 init-dex [--max-gas N]` | Create the `grad` DEX and list `GRAD` |
| `python -m hip3 list <mint> [--force]` | List a single perp for a tier 1+ coin |
| `python -m hip3 halt <COIN> [reason]` | Halt a market; positions settle at mark |
| `python -m hip3 resume <COIN>` | Resume a halted market |
| `python -m hip3 oracle [--dry-run]` | Run the oracle (primary or standby, from config) |
| `python -m hip3 add-oracle-signer <address> [--revoke]` | Allow or revoke a standby oracle key |
| `python -m hip3 apply-funding` | Re-apply funding settings to live markets |
| `python -m hip3 mm [--dry-run]` | Run the market maker |
| `python -m hip3 mm-cancel` | Pull every market maker order |
| `python -m hip3 manager [--once]` | Scan, rebalance, delist, watch the oracle |
| `python -m hip3 backtest <mint>` | Replay a coin's history through the HIP-3 mark rule |
| `python -m hip3 serve [--port N]` | Dashboard |
| `python -m hip3 status` / `auction` | The DEX and the slot auction as Hyperliquid sees them |
| `python -m hip3 economics` | Stake return calculator |
| `python -m hip3 tg-chatid` / `tg-test` | Set up and test Telegram |
| `python -m hip3 watchdog` | Oracle watchdog as its own process |

## Configuration

Settings live in [`config.json`](config.json), secrets in `.env`. Restart the processes after changes.

| Section | Key settings | Default |
|---|---|---|
| `dex` | `code`, `full_name`, `collateral_token`, `oracle_updater`, `fee_recipient` | `grad`, USDC (token 0) |
| `tiers.tier0/1/2` | market cap, liquidity, age, volume, hold time, leverage, OI cap | $500K / $500K / $5M |
| `safety` | pump.fun origin, top-10 holders, dev wallet, 1h pump filter | on, 30%, 5%, 300% |
| `index` | components, weight cap, rebalance period, base level | 50, 10%, 24 h, 1000 |
| `oracle` | `sources`, `min_sources`, interval, EMA, deviation limit, auto-halt, `standby_primary_url`, `failover_after_sec` | dexscreener + jupiter, 1, 3 s, 0.3, 15%, 120 s |
| `funding` | `multiplier`, `clamp_8h` | 1.0, 0.0006 |
| `fees` | `scale`, `growth_mode` | 1.0, off |
| `market_maker` | `enabled`, `markets`, levels, spreads, size, position limit, skew, requote | off, GRAD, 3 levels, 40 bps, $250, $5,000 |
| `delisting` | threshold ratio, hours, liquidity ratio, auto-halt | 50%, 24 h, 50%, on |
| `manager` | scan interval, auto-list tier 1, max single perps | 10 min, off, 10 |
| `dashboard` | `host`, `port` | 127.0.0.1, 8787 |
| `telegram` | `kinds`, `dedup_sec`, `watchdog_stale_sec`, `heartbeat_hours` | all, 300 s, 30 s, 12 h |

| `.env` variable | Purpose |
|---|---|
| `HL_NETWORK` / `HL_ALLOW_MAINNET` | `testnet` by default; mainnet also needs `HL_ALLOW_MAINNET=yes` |
| `HL_PRIVATE_KEY` / `HL_ACCOUNT_ADDRESS` | Deployer key, and the main account if the key is an agent wallet |
| `HL_ORACLE_PRIVATE_KEY` | Oracle updater key |
| `HL_MM_PRIVATE_KEY` / `HL_MM_ACCOUNT_ADDRESS` | Market maker account |
| `JUPITER_API_KEY` | Optional, higher Jupiter limits |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Alerts |

## What code cannot do

Some steps need money, an account, a signature or a lawyer. Each one is explained with links in [docs/06_OPERATIONS.md](docs/06_OPERATIONS.md).

- [ ] **Testnet funds.** Deposit once on mainnet, then claim from the [testnet faucet](https://hyperliquid.gitbook.io/hyperliquid-docs/onboarding/testnet-faucet).
- [ ] **The 500,000 HYPE stake** (~$45M). Crowdfund it through [Kinetiq Launch](https://kinetiq.xyz/launch), bring in a partner, or stake your own.
- [ ] **A server near Hyperliquid.** Tokyo has the lowest latency: [AWS Lightsail](https://aws.amazon.com/lightsail/), [Vultr](https://www.vultr.com/). A second provider for the standby: [Hetzner](https://www.hetzner.com/cloud), [DigitalOcean](https://www.digitalocean.com/).
- [ ] **A private Solana RPC**: [Helius](https://www.helius.dev/), [QuickNode](https://www.quicknode.com/chains/sol), [Triton](https://triton.one/).
- [ ] **Market-making capital or partners.** The built-in bot is a start; deep books need professional market makers.
- [ ] **A trading front end** with a [builder code](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/builder-codes), built on [@nktkas/hyperliquid](https://github.com/nktkas/hyperliquid).
- [ ] **Legal advice** on where to operate, terms of use, and [HIP-3\*](https://x.com/HyperliquidX/status/2114772826435866711) allowlists if KYC is needed.
- [ ] **A public oracle methodology** and listing policy, so traders and stakers know the rules.

## Project layout

```text
HIP-3/
├── hip3/                     Python package (python -m hip3)
│   ├── __main__.py           CLI
│   ├── doctor.py             preflight checks
│   ├── scanner.py            discovery, metrics, tiers
│   ├── index.py              GRAD weights and chained level
│   ├── listing.py            init-dex, list, halt, funding, oracle signers
│   ├── oracle.py             multi-source oracle with standby mode
│   ├── mm.py                 market maker
│   ├── manager.py            scan loop, delistings, listing candidates
│   ├── watchdog.py           alerts when the oracle goes quiet
│   ├── backtest.py           mark-lag replay on historical candles
│   ├── notify.py             Telegram
│   ├── hl_client.py          Hyperliquid info and signed perpDeploy actions
│   ├── pricing.py            median, bundles, price formatting
│   ├── server.py             dashboard and /api/health
│   └── sources/              pump.fun, DexScreener, Jupiter, Solana RPC, on-chain pools
├── web/                      dashboard
├── tests/                    pytest suite
├── deploy/                   VPS setup script, systemd units
├── economics/model.py        stake return calculator
├── docs/                     concept, rules, policy, economics, roadmap, operations
├── .github/workflows/ci.yml  tests and Docker build on every push
├── Dockerfile, docker-compose.yml
├── config.json, .env.example
└── *.bat                     Windows launchers
```

## Risks and limits

- **Stake at risk.** A bad oracle input can be slashed by up to 100% of 500,000 HYPE, whether the cause is malice, a bug or a stolen key. Keep the oracle key separate and the deployer key offline.
- **Rugs outrun the mark.** Hyperliquid moves a HIP-3 mark at most 1% per update, so in a −90% crash positions sit on a stale price for a while. Leverage stays low and margin isolated for this reason. `backtest` shows how bad it would have been for a given coin.
- **Market maker inventory.** The bot can end up holding a position in a coin that rugs. `max_position_usd` limits the damage; size it to what you can lose.
- **Data dependencies.** The pump.fun API is unofficial and may change; the scanner falls back to DexScreener alone. Run the oracle with at least two sources on mainnet.
- **Start on testnet.** Run every market there before mainnet, including halts, failover and the market maker.
- **Not financial or legal advice.** Perpetual futures on memecoins can wipe out a trader's margin, and whether you may operate such a market depends on where you and your users are.

## Documentation

| Document | Contents |
|---|---|
| [01 Concept](docs/01_CONCEPT.md) | The idea, the niche, the main problem and its answer |
| [02 HIP-3 rules](docs/02_HIP3_RULES.md) | Stake, auction, oracle, margin, fees and slashing, with sources |
| [03 Listing policy](docs/03_LISTING_POLICY.md) | Tier criteria, index rules, delisting and oracle stops |
| [04 Economics](docs/04_ECONOMICS.md) | Fee model, scenarios and break-even |
| [05 Roadmap](docs/05_ROADMAP.md) | What is done, what is next, risk register |
| [06 Operations](docs/06_OPERATIONS.md) | Funds, stake, servers, RPC, liquidity, front end, legal |

## Links

- Hyperliquid: [HIP-3](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals), [deployer actions](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/hip-3-deployer-actions), [fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees), [API wallets](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/nonces-and-api-wallets), [builder codes](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/builder-codes), [testnet faucet](https://hyperliquid.gitbook.io/hyperliquid-docs/onboarding/testnet-faucet)
- SDKs: [hyperliquid-python-sdk](https://github.com/hyperliquid-dex/hyperliquid-python-sdk), [@nktkas/hyperliquid](https://github.com/nktkas/hyperliquid)
- Data: [DexScreener API](https://docs.dexscreener.com/api/reference), [Jupiter Price API](https://dev.jup.ag/docs/price-api/v3), [GeckoTerminal API](https://www.geckoterminal.com/dex-api)
- Capital: [Kinetiq Launch](https://kinetiq.xyz/launch)
- Infrastructure: [AWS Lightsail](https://aws.amazon.com/lightsail/), [Vultr](https://www.vultr.com/), [Hetzner](https://www.hetzner.com/cloud), [Helius](https://www.helius.dev/), [QuickNode](https://www.quicknode.com/chains/sol)
- [Telegram Bot API](https://core.telegram.org/bots/api)

## License

[MIT](LICENSE). HyperGrad is an independent project and is not affiliated with Hyperliquid, pump.fun or trade.xyz.
