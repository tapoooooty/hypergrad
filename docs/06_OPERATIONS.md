# Operations: what code cannot do

Everything below needs a person, money, an account or a signature. Work through it in this order.

## 1. Testnet funds

1. Make a Hyperliquid account and deposit once on mainnet. The testnet faucet only serves wallets that have deposited on mainnet before.
2. Claim mock USDC from the [testnet faucet](https://hyperliquid.gitbook.io/hyperliquid-docs/onboarding/testnet-faucet).
3. Use separate wallets for the deployer, the oracle and the market maker. Hyperliquid [API wallets](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/nonces-and-api-wallets) let a server sign without holding the main key.
4. Run `python -m hip3 doctor`. It reports the testnet stake it can see; then try `init-dex`.

## 2. The 500,000 HYPE stake

The mainnet DEX cannot exist without it. Options:

| Route | What it involves | Link |
|---|---|---|
| Crowdfunded stake | Kinetiq Launch pools HYPE from stakers into a deployer-specific LST and shares your fees with them | [kinetiq.xyz/launch](https://kinetiq.xyz/launch) |
| Strategic partner | A fund or HYPE holder stakes in exchange for revenue share or equity | [hyperliquid.xyz](https://hyperliquid.xyz) |
| Own capital | Buy and stake 500k HYPE, locked at least 183 days | [Staking docs](https://hyperliquid.gitbook.io/hyperliquid-docs/hypercore/staking) |

Bring a working testnet market, this repository and the [listing policy](03_LISTING_POLICY.md) to those conversations. They answer the first three questions every staker asks.

## 3. Servers

The oracle has to run without interruption. A home PC is not enough.

| Provider | Why | Link |
|---|---|---|
| AWS (Tokyo, ap-northeast-1) | Tokyo is close to Hyperliquid's infrastructure; lowest latency | [aws.amazon.com/lightsail](https://aws.amazon.com/lightsail/) |
| Vultr (Tokyo) | Cheap, hourly billing, Tokyo region | [vultr.com](https://www.vultr.com/) |
| Hetzner | Best price for the backup oracle and dashboard | [hetzner.com/cloud](https://www.hetzner.com/cloud) |
| DigitalOcean | Simple dashboard, good docs | [digitalocean.com](https://www.digitalocean.com/) |

Suggested layout: primary oracle, manager and market maker on a Tokyo VPS (2 vCPU, 4 GB RAM is plenty). Standby oracle on a second provider in another region, with `oracle.standby_primary_url` pointing at the primary.

Setup on a fresh Ubuntu server:

```bash
scp -r ./HIP-3/* root@SERVER:/opt/hypergrad/
ssh root@SERVER 'bash /opt/hypergrad/deploy/vps-setup.sh'
ssh root@SERVER 'nano /opt/hypergrad/.env'
ssh root@SERVER 'cd /opt/hypergrad && docker compose run --rm oracle doctor && docker compose up -d'
ssh -L 8787:localhost:8787 root@SERVER   # dashboard at http://localhost:8787
```

Use SSH keys rather than passwords, and keep `.env` readable by root only (the setup script does `chmod 600`).

## 4. Solana RPC

The public endpoint rate-limits holder checks and cannot carry the on-chain oracle source. Pick one:

| Provider | Link |
|---|---|
| Helius | [helius.dev](https://www.helius.dev/) |
| QuickNode | [quicknode.com](https://www.quicknode.com/chains/sol) |
| Triton One | [triton.one](https://triton.one/) |

Put the URL in `sources.solana_rpc` in config.json, then add `"onchain"` to `oracle.sources`.

## 5. Liquidity

`python -m hip3 mm` quotes your markets, but a book that traders trust needs more depth than one bot with a few thousand dollars.

- Start with the built-in market maker on testnet and on mainnet launch day.
- Talk to professional market makers active on Hyperliquid and offer fee rebates or a share of deployer revenue.
- Hyperliquid's [builder codes](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/builder-codes) let a trading front end charge its own fee; you can share it with liquidity partners.

## 6. A trading front end

Traders need somewhere to click. HIP-3 markets are reachable through the Hyperliquid API, and the dashboard here is read-only. For a branded trading screen:

- [@nktkas/hyperliquid](https://github.com/nktkas/hyperliquid) is a TypeScript SDK that signs orders in the browser.
- Register a [builder code](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/builder-codes) so every order placed through your UI pays you a fee.
- Wallet connection: [RainbowKit](https://www.rainbowkit.com/) or [wagmi](https://wagmi.sh/).

## 7. Legal

Perpetual futures on memecoins are regulated in many countries. Before mainnet:

- Get advice on where you can operate and which users to block.
- Publish terms of use and a risk disclosure.
- Plan for [HIP-3\*](https://x.com/HyperliquidX/status/2114772826435866711) allowlists if you need KYC.

## 8. Trust

- Publish the oracle methodology (sources, median, freeze and halt rules). [docs/03_LISTING_POLICY.md](03_LISTING_POLICY.md) is a good start.
- Announce listings and halts in a public channel. The Telegram alerts can post to one directly.
- Run `python -m hip3 backtest <mint>` on every coin before giving it its own perp, and keep the results.
