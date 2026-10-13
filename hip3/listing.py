"""Listing and delisting markets on our HIP-3 DEX."""
import time

from . import index as gindex
from . import state
from .config import CFG, DEX
from .hl_client import Deployer
from .pricing import choose_multiplier, format_px, sanitize_ticker, sz_decimals_for

# Margin tables with id < 50 are Hyperliquid's default single-tier tables: id = max leverage.
# For a custom multi-tier table, create it with insertMarginTable and use its id instead.


def _setup_market(dep: Deployer, coin: str, oi_cap: int) -> None:
    dep.set_margin_modes({coin: "strictIsolated"})
    dep.set_oi_caps({coin: max(1_000_000, int(oi_cap))})
    fund = CFG.get("funding", {})
    try:
        if fund.get("multiplier"):
            dep.set_funding_multipliers({coin: str(fund["multiplier"])})
        if fund.get("clamp_8h"):
            dep.set_funding_clamps({coin: str(fund["clamp_8h"])})
    except RuntimeError as e:
        state.log_event("warn", f"Funding settings for {coin} not set: {e}")
    fee_cfg = CFG.get("fees", {"scale": "1.0", "growth_mode": False})
    try:
        dep.set_deployer_fees(coin, str(fee_cfg["scale"]), bool(fee_cfg["growth_mode"]))
    except RuntimeError as e:  # allowed once per 30 days, not critical
        state.log_event("warn", f"Fees for {coin} not set: {e}")


def init_dex(max_gas: int | None = None) -> None:
    """First run: create the DEX and register the GRAD index as its first asset."""
    markets = state.load("markets")
    sym = CFG["index"]["symbol"]
    if sym in markets:
        print(f"{DEX}:{sym} is already registered")
        return
    idx = gindex.rebalance(state.load("candidates"), force=True)
    if not idx.get("units"):
        raise SystemExit("The index is empty. Run `scan` first: GRAD needs at least one tier-0 coin.")
    level = idx["level"]
    szd = sz_decimals_for(level)
    dep = Deployer()
    schema = {"fullName": CFG["dex"]["full_name"], "collateralToken": CFG["dex"]["collateral_token"]}
    if CFG["dex"].get("oracle_updater"):
        schema["oracleUpdater"] = CFG["dex"]["oracle_updater"]
    res = dep.register_asset(sym, szd, format_px(level, szd), CFG["index"]["max_leverage"], max_gas, schema)
    state.log_event("listing", f"DEX {DEX} created, {DEX}:{sym} registered", response=str(res)[:300])
    _setup_market(dep, sym, CFG["index"]["oi_cap_usd"])
    if CFG["dex"].get("fee_recipient"):
        dep.set_fee_recipient(CFG["dex"]["fee_recipient"])
    dep.annotate(
        sym,
        "meme index",
        "Index of Solana memecoins that graduated from pump.fun (market cap ≥ $500K). Weights ∝ √liquidity, capped at 10%.",
        sym,
        ["meme", "solana"],
    )
    markets[sym] = {"kind": "index", "sz_decimals": szd, "multiplier": 1, "status": "live", "listed_at": int(time.time())}
    state.save("markets", markets)


def list_coin(mint: str, max_gas: int | None = None, force: bool = False) -> str:
    c = state.load("candidates").get(mint)
    if not c:
        raise SystemExit("Coin not found in candidates.json. Run `scan` first.")
    if c.get("tier") not in ("tier1", "tier2") and not force:
        raise SystemExit(f"{c['symbol']} is {c.get('tier') or 'watch'}; single perps start at tier1 (or pass --force)")
    markets = state.load("markets")
    if any(m.get("mint") == mint for m in markets.values()):
        raise SystemExit("Already listed")
    if CFG["index"]["symbol"] not in markets:
        raise SystemExit("Run init-dex first")
    tier = c.get("tier") or "tier1"
    tcfg = CFG["tiers"][tier]
    mult, prefix = choose_multiplier(c["price_usd"])
    coin = sanitize_ticker(c["symbol"], prefix, set(markets))
    px = c["price_usd"] * mult
    szd = sz_decimals_for(px)
    dep = Deployer()
    res = dep.register_asset(coin, szd, format_px(px, szd), tcfg["max_leverage"], max_gas, None)
    state.log_event("listing", f"Listed {DEX}:{coin} ({c['symbol']}, ×{mult:,})", mint=mint, response=str(res)[:300])
    _setup_market(dep, coin, tcfg["oi_cap_usd"])
    dep.annotate(
        coin,
        "solana meme",
        f"{c['name']} ({c['symbol']}), mint {mint}. 1 contract = {mult:,} tokens. "
        "Oracle: liquidity-weighted median of Solana pools.",
        coin,
        ["meme", "solana"],
    )
    markets[coin] = {
        "kind": "single",
        "mint": mint,
        "symbol": c["symbol"],
        "multiplier": mult,
        "sz_decimals": szd,
        "tier": tier,
        "status": "live",
        "listed_at": int(time.time()),
    }
    state.save("markets", markets)
    return coin


def halt_market(coin: str, reason: str, dep: Deployer | None = None) -> None:
    markets = state.load("markets")
    if coin not in markets or markets[coin]["status"] == "halted":
        return
    (dep or Deployer()).halt(coin, True)
    markets[coin].update(status="halted", halted_at=int(time.time()), halt_reason=reason)
    state.save("markets", markets)
    state.log_event("halt", f"{DEX}:{coin} halted and settled at mark: {reason}")


def add_oracle_signer(address: str, allowed: bool = True) -> None:
    """Let a second key (standby oracle) send setOracle for this DEX."""
    Deployer().set_sub_deployer("setOracle", address, allowed)
    state.log_event("oracle", f"{'Allowed' if allowed else 'Revoked'} oracle signer {address}")


def apply_funding(coins: list[str] | None = None) -> None:
    """Re-apply config.json funding settings to live markets."""
    dep = Deployer()
    fund = CFG.get("funding", {})
    coins = coins or [c for c, m in state.load("markets").items() if m.get("status") == "live"]
    if fund.get("multiplier"):
        dep.set_funding_multipliers({c: str(fund["multiplier"]) for c in coins})
    if fund.get("clamp_8h"):
        dep.set_funding_clamps({c: str(fund["clamp_8h"]) for c in coins})
    state.log_event("oracle", f"Funding settings applied to {', '.join(coins)}")


def resume_market(coin: str) -> None:
    markets = state.load("markets")
    Deployer().halt(coin, False)
    markets[coin]["status"] = "live"
    state.save("markets", markets)
    state.log_event("listing", f"{DEX}:{coin} is trading again")
