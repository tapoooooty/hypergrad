"""Preflight checks: python -m hip3 doctor

Runs every check it can without sending a transaction and prints PASS, WARN or FAIL
with the fix for each problem. Exit code 1 if anything failed.
"""
import importlib.metadata as md
import sys
import time

from . import hl_client, state
from .config import API_URL, CFG, DEX, NETWORK, ROOT, env
from .http import get_json, post_json

STAKE_REQUIRED = 500_000
RESULTS: list[tuple[str, str, str, str]] = []


def _add(status: str, area: str, check: str, detail: str) -> None:
    RESULTS.append((status, area, check, detail))


def _address(key_env: str) -> str | None:
    key = env(key_env)
    if not key:
        return None
    try:
        from eth_account import Account

        return Account.from_key(key).address
    except Exception as e:
        _add("FAIL", "keys", key_env, f"not a valid private key ({e.__class__.__name__})")
        return None


def check_environment() -> None:
    v = sys.version_info
    _add("PASS" if v >= (3, 10) else "FAIL", "env", "python", f"{v.major}.{v.minor}.{v.micro} (need 3.10+)")
    for pkg in ("hyperliquid-python-sdk", "eth-account", "requests"):
        try:
            _add("PASS", "env", pkg, md.version(pkg))
        except md.PackageNotFoundError:
            _add("FAIL", "env", pkg, "not installed. Run setup.bat or pip install -r requirements.txt")
    _add("PASS" if (ROOT / ".env").exists() else "FAIL", "env", ".env", "found" if (ROOT / ".env").exists() else "missing. Copy .env.example to .env")


def check_config() -> None:
    dex = CFG["dex"]["code"]
    ok = dex.isalpha() and dex.islower() and 2 <= len(dex) <= 4
    _add("PASS" if ok else "FAIL", "config", "dex.code", f"'{dex}'" + ("" if ok else " must be 2-4 lowercase letters"))
    t = CFG["tiers"]
    ordered = t["tier0"]["min_mcap_usd"] <= t["tier1"]["min_mcap_usd"] < t["tier2"]["min_mcap_usd"]
    _add("PASS" if ordered else "FAIL", "config", "tier thresholds", "increasing" if ordered else "tier0 <= tier1 < tier2 is required")
    for name in ("tier1", "tier2"):
        cap = t[name]["oi_cap_usd"]
        _add("PASS" if cap >= 1_000_000 else "FAIL", "config", f"{name}.oi_cap_usd", f"${cap:,} (protocol minimum $1,000,000)")
        lev = t[name]["max_leverage"]
        _add("PASS" if 1 <= lev <= 50 else "FAIL", "config", f"{name}.max_leverage", f"{lev}x")
    interval = CFG["oracle"]["update_interval_sec"]
    _add("PASS" if interval >= 2.5 else "FAIL", "config", "oracle.update_interval_sec", f"{interval}s (protocol minimum 2.5s)")
    if CFG.get("fees", {}).get("growth_mode"):
        _add("WARN", "config", "fees.growth_mode", "on: deployer revenue drops about 10x")


def check_network(addr: str | None) -> None:
    _add("PASS" if NETWORK in ("testnet", "mainnet") else "FAIL", "hyperliquid", "network", NETWORK)
    if NETWORK == "mainnet":
        _add("PASS" if env("HL_ALLOW_MAINNET") == "yes" else "WARN", "hyperliquid", "HL_ALLOW_MAINNET",
             "yes" if env("HL_ALLOW_MAINNET") == "yes" else "not set: every signed action will be refused")
    try:
        t0 = time.time()
        dexs = [d for d in hl_client.perp_dexs() if d]
        _add("PASS", "hyperliquid", "API", f"{API_URL} answered in {1000 * (time.time() - t0):.0f} ms, {len(dexs)} HIP-3 DEXs")
    except Exception as e:
        _add("FAIL", "hyperliquid", "API", f"{API_URL} unreachable: {e}")
        return

    mine = next((d for d in dexs if d.get("name") == DEX), None)
    if mine:
        deployer = (mine.get("deployer") or "").lower()
        if addr and deployer == (env("HL_ACCOUNT_ADDRESS") or addr).lower():
            _add("PASS", "hyperliquid", f"DEX '{DEX}'", "exists and belongs to this deployer")
        else:
            _add("FAIL" if not state.load("markets") else "WARN", "hyperliquid", f"DEX '{DEX}'",
                 f"already taken by {deployer or 'another address'}. Pick a new dex.code in config.json")
    else:
        _add("PASS", "hyperliquid", f"DEX '{DEX}'", "name is free; init-dex will create it")

    try:
        a = hl_client.auction_status()
        price = a.get("currentGas") or a.get("startGas")
        _add("PASS", "hyperliquid", "slot auction", f"current price {price} HYPE (first 3 assets of a new DEX are free)")
    except Exception as e:
        _add("WARN", "hyperliquid", "slot auction", f"could not read: {e}")


def check_account(addr: str | None) -> None:
    if not addr:
        _add("FAIL", "keys", "HL_PRIVATE_KEY", "missing. Add the deployer key to .env")
        return
    acct = env("HL_ACCOUNT_ADDRESS") or addr
    _add("PASS", "keys", "deployer", acct + ("" if acct == addr else f" (signing with agent {addr})"))
    try:
        s = hl_client.info({"type": "delegatorSummary", "user": acct})
        staked = float(s.get("delegated") or 0)
        need = STAKE_REQUIRED if NETWORK == "mainnet" else None
        if need and staked < need:
            _add("FAIL", "stake", "staked HYPE", f"{staked:,.0f} of {need:,} required for a mainnet DEX")
        else:
            _add("PASS" if staked else "WARN", "stake", "staked HYPE",
                 f"{staked:,.0f}" + ("" if need else " (testnet requirement: check the HIP-3 docs or try init-dex)"))
    except Exception as e:
        _add("WARN", "stake", "staked HYPE", f"could not read: {e}")
    try:
        spot = hl_client.info({"type": "spotClearinghouseState", "user": acct})
        bal = {b["coin"]: float(b["total"]) for b in spot.get("balances", [])}
        _add("PASS" if bal.get("HYPE", 0) > 0 else "WARN", "balances", "HYPE (spot)", f"{bal.get('HYPE', 0):,.2f} (pays gas for auction slots)")
        _add("PASS" if bal.get("USDC", 0) > 0 else "WARN", "balances", "USDC (spot)", f"{bal.get('USDC', 0):,.2f}")
    except Exception as e:
        _add("WARN", "balances", "spot", f"could not read: {e}")

    upd = CFG["dex"].get("oracle_updater")
    oracle_addr = _address("HL_ORACLE_PRIVATE_KEY")
    if oracle_addr and upd and oracle_addr.lower() != upd.lower():
        _add("FAIL", "keys", "oracle updater", f"HL_ORACLE_PRIVATE_KEY is {oracle_addr} but config says {upd}")
    elif oracle_addr and not upd:
        _add("WARN", "keys", "oracle updater", f"set dex.oracle_updater to {oracle_addr} before init-dex")
    elif not oracle_addr:
        _add("WARN", "keys", "oracle updater", "no separate oracle key; the deployer key will sign every 3 s")
    else:
        _add("PASS", "keys", "oracle updater", oracle_addr)

    mm = _address("HL_MM_PRIVATE_KEY")
    if CFG.get("market_maker", {}).get("enabled"):
        if not mm:
            _add("FAIL", "keys", "market maker", "market_maker.enabled is true but HL_MM_PRIVATE_KEY is empty")
        elif mm.lower() == acct.lower():
            _add("WARN", "keys", "market maker", "uses the deployer account; a separate account is safer")
        else:
            _add("PASS", "keys", "market maker", mm)


def check_sources() -> None:
    try:
        get_json("https://api.dexscreener.com/token-profiles/latest/v1", retries=1)
        _add("PASS", "sources", "DexScreener", "reachable")
    except Exception as e:
        _add("FAIL", "sources", "DexScreener", str(e)[:120])
    try:
        get_json("https://frontend-api-v3.pump.fun/coins", params={"limit": 1, "offset": 0, "sort": "market_cap", "order": "DESC"}, retries=1)
        _add("PASS", "sources", "pump.fun API", "reachable")
    except Exception:
        _add("WARN", "sources", "pump.fun API", "unreachable; the scanner falls back to DexScreener")
    rpc = CFG["sources"]["solana_rpc"]
    try:
        r = post_json(rpc, {"jsonrpc": "2.0", "id": 1, "method": "getHealth"}, retries=1)
        public = "mainnet-beta.solana.com" in rpc
        _add("WARN" if public else "PASS", "sources", "Solana RPC",
             f"{r.get('result', r.get('error'))}" + (" (public RPC: fine for testing, too slow for the on-chain oracle source)" if public else ""))
    except Exception as e:
        _add("FAIL", "sources", "Solana RPC", str(e)[:120])
    if "jupiter" in CFG["oracle"].get("sources", []):
        try:
            from .sources import jupiter

            px = jupiter.prices(["So11111111111111111111111111111111111111112"])
            _add("PASS" if px else "WARN", "sources", "Jupiter price API", "reachable" if px else "answered without a SOL price")
        except Exception as e:
            _add("WARN", "sources", "Jupiter price API", str(e)[:120])


def check_telegram() -> None:
    from . import notify

    if not notify.TOKEN:
        _add("WARN", "alerts", "Telegram", "not configured; you will not hear about freezes or halts")
        return
    try:
        me = get_json(f"https://api.telegram.org/bot{notify.TOKEN}/getMe", retries=1)
        name = me.get("result", {}).get("username")
        _add("PASS" if notify.CHAT_IDS else "WARN", "alerts", "Telegram",
             f"bot @{name}" + ("" if notify.CHAT_IDS else ", but TELEGRAM_CHAT_ID is empty (run tg-chatid)"))
    except Exception:
        _add("FAIL", "alerts", "Telegram", "bot token rejected")


def check_state() -> None:
    cands = state.load("candidates")
    idx = state.load("index")
    _add("PASS" if cands else "WARN", "state", "candidates", f"{len(cands)} coins" if cands else "empty. Run scan or start the manager")
    n = len(idx.get("weights", {}))
    _add("PASS" if n else "WARN", "state", "GRAD index", f"{n} components" if n else "empty. init-dex needs at least one tier-0 coin")
    alive = state.load("oracle_alive").get("ts")
    if state.load("markets"):
        age = time.time() - (alive or 0)
        _add("PASS" if age < 15 else "FAIL", "state", "oracle", f"last push {age:.0f}s ago" if alive else "has never pushed")


def run() -> int:
    addr = _address("HL_PRIVATE_KEY")
    for fn in (check_environment, check_config, lambda: check_network(addr), lambda: check_account(addr),
               check_sources, check_telegram, check_state):
        try:
            fn()
        except Exception as e:
            _add("FAIL", "doctor", getattr(fn, "__name__", "check"), f"crashed: {e}")
    colors = {"PASS": "\033[32m", "WARN": "\033[33m", "FAIL": "\033[31m"}
    reset = "\033[0m" if sys.stdout.isatty() else ""
    print(f"HyperGrad doctor, network {NETWORK}, dex {DEX}\n")
    for status, area, check, detail in RESULTS:
        c = colors[status] if reset else ""
        print(f"{c}{status:<5}{reset} {area:<12}{check:<26}{detail}")
    fails = sum(1 for r in RESULTS if r[0] == "FAIL")
    warns = sum(1 for r in RESULTS if r[0] == "WARN")
    print(f"\n{len(RESULTS)} checks: {fails} failed, {warns} warnings")
    return 1 if fails else 0
