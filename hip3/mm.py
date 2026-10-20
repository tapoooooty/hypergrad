"""Market maker: keeps a post-only ladder of bids and asks around the oracle price.

python -m hip3 mm [--dry-run]

For every market in config.json -> market_maker.markets:
  fair      local oracle price when fresh, otherwise Hyperliquid's oraclePx
  spread    base_spread_bps, widened by recent volatility
  skew      the whole ladder shifts against the current position, up to skew_bps_at_max
  limits    no new bids above +max_position_usd, no new asks below -max_position_usd
  stops     every order is pulled when the market is halted, the oracle freezes or goes stale

Orders are ALO (add liquidity only), so the bot never crosses the book and never pays taker fees.
Use a separate account funded with USDC: HL_MM_PRIVATE_KEY (and HL_MM_ACCOUNT_ADDRESS for an agent key).
"""
import math
import signal
import statistics
import sys
import time
from collections import deque

from . import hl_client, state
from .config import CFG, DEX, NETWORK, env
from .pricing import format_px

MCFG = CFG["market_maker"]


def _round_size(sz: float, sz_decimals: int) -> float:
    q = 10 ** sz_decimals
    return math.floor(sz * q) / q


class MarketMaker:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.fair_hist: dict[str, deque] = {}
        self.last_quote: dict[str, tuple[float, float]] = {}
        self.ex = None
        self.user = env("HL_MM_ACCOUNT_ADDRESS")
        if not dry_run:
            from eth_account import Account
            from hyperliquid.exchange import Exchange
            from hyperliquid.utils import constants

            key = env("HL_MM_PRIVATE_KEY")
            if not key:
                raise SystemExit("Set HL_MM_PRIVATE_KEY in .env (a separate account funded with USDC)")
            if NETWORK == "mainnet" and env("HL_ALLOW_MAINNET") != "yes":
                raise SystemExit("Mainnet is locked. Set HL_ALLOW_MAINNET=yes in .env to proceed.")
            wallet = Account.from_key(key)
            base = constants.MAINNET_API_URL if NETWORK == "mainnet" else constants.TESTNET_API_URL
            try:
                self.ex = Exchange(wallet, base, account_address=self.user, perp_dexs=["", DEX])
            except TypeError:
                self.ex = Exchange(wallet, base, account_address=self.user)
            self.user = self.user or wallet.address
        self.coins = [f"{DEX}:{c}" for c in MCFG["markets"]]

    # --- reads ------------------------------------------------------------
    def _venue(self) -> dict[str, dict]:
        meta, ctxs = hl_client.dex_meta(DEX)
        return {a["name"]: {"szDecimals": a.get("szDecimals", 0), **c} for a, c in zip(meta["universe"], ctxs)}

    def _positions(self) -> dict[str, float]:
        if not self.user:
            return {}
        cs = hl_client.info({"type": "clearinghouseState", "user": self.user, "dex": DEX})
        return {p["position"]["coin"]: float(p["position"]["szi"]) for p in cs.get("assetPositions", [])}

    def _open_orders(self) -> list[dict]:
        if not self.user:
            return []
        return hl_client.info({"type": "openOrders", "user": self.user, "dex": DEX})

    def _fair(self, coin: str, venue: dict) -> float | None:
        short = coin.split(":", 1)[1]
        market = state.load("markets").get(short, {})
        if market and market.get("status") != "live":
            return None
        rec = state.load("oracle").get(short, {})
        if rec.get("frozen_since"):
            return None
        if rec.get("spot") and time.time() - rec.get("ts", 0) <= MCFG["max_oracle_age_sec"]:
            return float(rec["spot"])
        v = venue.get(coin) or {}
        px = v.get("oraclePx") or v.get("markPx")
        return float(px) if px else None

    # --- quoting ----------------------------------------------------------
    def _spread_bps(self, coin: str, fair: float) -> float:
        h = self.fair_hist.setdefault(coin, deque(maxlen=120))
        h.append(fair)
        if len(h) < 10:
            return MCFG["base_spread_bps"] * 2
        rets = [math.log(b / a) for a, b in zip(list(h)[:-1], list(h)[1:]) if a > 0 and b > 0]
        per_min = statistics.pstdev(rets) * math.sqrt(60 / MCFG["loop_sec"]) * 1e4
        return MCFG["base_spread_bps"] + MCFG["vol_spread_mult"] * per_min

    def _ladder(self, coin: str, fair: float, pos: float, szd: int) -> list[dict]:
        pos_usd = pos * fair
        ratio = max(-1.0, min(1.0, pos_usd / MCFG["max_position_usd"]))
        mid = fair * (1 - MCFG["skew_bps_at_max"] * ratio / 1e4)
        half = self._spread_bps(coin, fair) / 2
        orders = []
        for i in range(MCFG["levels"]):
            off = (half + i * MCFG["level_spacing_bps"]) / 1e4
            for is_buy, px in ((True, mid * (1 - off)), (False, mid * (1 + off))):
                if is_buy and pos_usd >= MCFG["max_position_usd"]:
                    continue
                if not is_buy and pos_usd <= -MCFG["max_position_usd"]:
                    continue
                sz = _round_size(MCFG["order_size_usd"] / px, szd)
                if sz <= 0:
                    continue
                orders.append({
                    "coin": coin,
                    "is_buy": is_buy,
                    "sz": sz,
                    "limit_px": float(format_px(px, szd)),
                    "order_type": {"limit": {"tif": "Alo"}},
                    "reduce_only": False,
                })
        return orders

    def _cancel_coin(self, coin: str, orders: list[dict]) -> None:
        mine = [{"coin": coin, "oid": o["oid"]} for o in orders if o.get("coin") == coin]
        if mine and not self.dry_run:
            self.ex.bulk_cancel(mine)

    def cancel_all(self) -> None:
        if self.dry_run:
            return
        try:
            orders = self._open_orders()
            mine = [{"coin": o["coin"], "oid": o["oid"]} for o in orders if o.get("coin") in self.coins]
            if mine:
                self.ex.bulk_cancel(mine)
                state.log_event("mm", f"Market maker pulled {len(mine)} orders")
        except Exception as e:
            state.log_event("error", f"Market maker could not cancel orders: {e}")

    def setup(self) -> None:
        if self.dry_run:
            return
        for coin in self.coins:
            try:
                self.ex.update_leverage(MCFG["leverage"], coin, False)
            except Exception as e:
                state.log_event("warn", f"Market maker leverage for {coin} not set: {e}")

    def tick(self) -> None:
        venue = self._venue()
        positions = self._positions()
        orders = self._open_orders()
        now = time.time()
        for coin in self.coins:
            fair = self._fair(coin, venue)
            if fair is None:
                if any(o.get("coin") == coin for o in orders):
                    self._cancel_coin(coin, orders)
                    state.log_event("mm", f"{coin}: quotes pulled (halted, frozen or stale oracle)")
                continue
            last_fair, last_t = self.last_quote.get(coin, (0.0, 0.0))
            moved = abs(fair / last_fair - 1) * 1e4 if last_fair else 1e9
            resting = [o for o in orders if o.get("coin") == coin]
            if resting and moved < MCFG["requote_bps"] and now - last_t < MCFG["requote_sec"]:
                continue
            szd = int((venue.get(coin) or {}).get("szDecimals", 0))
            ladder = self._ladder(coin, fair, positions.get(coin, 0.0), szd)
            self._cancel_coin(coin, orders)
            if self.dry_run:
                print(f"[{time.strftime('%H:%M:%S')}] dry-run {coin} fair {fair:.5g} pos {positions.get(coin, 0)}: "
                      + "  ".join(f"{'B' if o['is_buy'] else 'A'} {o['sz']}@{o['limit_px']}" for o in ladder), flush=True)
            elif ladder:
                res = self.ex.bulk_orders(ladder)
                errs = [s.get("error") for s in (res.get("response", {}).get("data", {}).get("statuses", []) if isinstance(res, dict) else []) if isinstance(s, dict) and s.get("error")]
                if errs:
                    state.log_event("warn", f"{coin}: {len(errs)} quotes rejected, first: {errs[0]}")
                print(f"[{time.strftime('%H:%M:%S')}] {coin} fair {fair:.5g} pos {positions.get(coin, 0)}: {len(ladder) - len(errs)} quotes", flush=True)
            self.last_quote[coin] = (fair, now)

    def run(self) -> None:
        if not MCFG.get("enabled") and not self.dry_run:
            raise SystemExit("market_maker.enabled is false in config.json")

        def stop(*_):
            self.cancel_all()
            sys.exit(0)

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        self.setup()
        state.log_event("mm", f"Market maker started on {', '.join(self.coins)} ({'dry-run' if self.dry_run else NETWORK})")
        errors = 0
        while True:
            started = time.time()
            try:
                self.tick()
                errors = 0
            except Exception as e:
                errors += 1
                state.log_event("error", f"Market maker tick failed: {e}")
                if errors >= 5:
                    self.cancel_all()
                    time.sleep(30)
            time.sleep(max(0.5, MCFG["loop_sec"] - (time.time() - started)))
