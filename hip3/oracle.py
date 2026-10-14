"""Oracle daemon: computes prices every ~3s and sends setOracle.

Sources (config.json -> oracle.sources), each one gets one vote:
  dexscreener  liquidity-weighted median of every Solana pool DexScreener lists
  jupiter      Jupiter Price API v3, aggregated across routes
  onchain      reserves read straight from the coin's largest PumpSwap pool over Solana RPC

spot = median of the available source prices. mark = EMA of spot (the protocol also caps mark
moves at 1% per update). If fewer than min_sources answer, or they disagree by more than
max_source_deviation_pct, the price freezes; a long freeze halts the market.

Standby mode: set oracle.standby_primary_url to the primary's dashboard URL. The standby
computes prices every tick but only sends them while the primary looks unhealthy.
Its key must be allowed to set prices: python -m hip3 add-oracle-signer <address>.
"""
import statistics
import time
from collections import deque

from . import index as gindex
from . import state
from .config import CFG, DEX
from .hl_client import Deployer
from .http import get_json
from .listing import halt_market
from .pricing import ema, format_px, source_deviation_pct, weighted_median
from .sources import dexscreener, jupiter, onchain
from .sources.solana_rpc import SolanaRPC

OCFG = CFG["oracle"]


class Oracle:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.dep = None if dry_run else Deployer(key_env="HL_ORACLE_PRIVATE_KEY")
        self.st = state.load("oracle")
        self.spot_hist: dict[str, deque] = {}
        self.sources = OCFG.get("sources", ["dexscreener"])
        self.rpc = SolanaRPC(CFG["sources"]["solana_rpc"]) if "onchain" in self.sources else None
        self.primary_url = OCFG.get("standby_primary_url")
        self.standby_active = False

    # --- prices -----------------------------------------------------------
    def _spots(self, mints: list[str]) -> dict[str, dict]:
        pairs = dexscreener.pairs_for_tokens(mints)
        per: dict[str, dict[str, float]] = {m: {} for m in mints}
        liq: dict[str, float] = {}
        inner_dev: dict[str, float] = {}
        for mint, ps in pairs.items():
            quotes = dexscreener.price_quotes(ps)
            liq[mint] = sum(w for _, w in quotes)
            px = weighted_median(quotes)
            if px is not None and "dexscreener" in self.sources:
                per[mint]["dexscreener"] = px
                inner_dev[mint] = source_deviation_pct(quotes, px)

        sol_usd = None
        if "jupiter" in self.sources or "onchain" in self.sources:
            try:
                jp = jupiter.prices(mints + [jupiter.SOL_MINT])
                sol_usd = jp.get(jupiter.SOL_MINT)
                if "jupiter" in self.sources:
                    for m in mints:
                        if m in jp:
                            per[m]["jupiter"] = jp[m]
            except Exception as e:
                state.log_event("warn", f"Jupiter price API failed: {e}")

        if self.rpc:
            for mint, ps in pairs.items():
                pools = onchain.pumpswap_pools(sorted(ps, key=lambda p: -((p.get("liquidity") or {}).get("usd") or 0)))
                if not pools:
                    continue
                try:
                    res = onchain.pool_price_usd(self.rpc, pools[0][0], mint, pools[0][1], sol_usd)
                    if res:
                        per[mint]["onchain"] = res[0]
                except Exception as e:
                    state.log_event("warn", f"On-chain read failed for {mint[:6]}: {str(e)[:120]}")

        out = {}
        for mint, src in per.items():
            if not src:
                continue
            vals = list(src.values())
            px = statistics.median(vals)
            dev = max(abs(v / px - 1) * 100 for v in vals) if len(vals) > 1 else 0.0
            dev = max(dev, inner_dev.get(mint, 0.0))
            out[mint] = {"px": px, "dev": dev, "liq": liq.get(mint, 0.0), "n": len(vals), "by_source": src}
        return out

    def _usable(self, s: dict | None) -> bool:
        return bool(s) and s["n"] >= OCFG.get("min_sources", 1) and s["dev"] <= OCFG["max_source_deviation_pct"]

    # --- standby ----------------------------------------------------------
    def _should_send(self) -> bool:
        if not self.primary_url:
            return True
        try:
            h = get_json(self.primary_url.rstrip("/") + "/api/health", retries=1, timeout=4)
            healthy = h.get("oracle_age") is not None and h["oracle_age"] <= OCFG.get("failover_after_sec", 10)
        except Exception:
            healthy = False
        if not healthy and not self.standby_active:
            state.log_event("watchdog", "Standby oracle took over: the primary is not publishing")
        if healthy and self.standby_active:
            state.log_event("watchdog", "Primary oracle is back; standby is idle again")
        self.standby_active = not healthy
        return not healthy

    # --- tick -------------------------------------------------------------
    def tick(self) -> None:
        now = time.time()
        markets = {k: v for k, v in state.load("markets").items() if v.get("status") == "live"}
        if not markets:
            return
        idx = state.load("index")
        mints = sorted({m["mint"] for m in markets.values() if m.get("mint")} | set(idx.get("units", {})))
        spots = self._spots(mints) if mints else {}

        # Emergency index removal when liquidity is pulled (rug)
        min_liq = 0.2 * CFG["tiers"]["tier0"]["min_liquidity_usd"]
        for mint in list(idx.get("units", {})):
            s = spots.get(mint)
            if s and s["liq"] and s["liq"] < min_liq:
                gindex.drop_component(mint, f"liquidity fell to ${s['liq']:,.0f}")
                idx = state.load("index")

        oracle_pxs, mark_pxs, ext_pxs = {}, {}, {}
        for coin, m in markets.items():
            rec = self.st.get(coin, {})
            if m["kind"] == "index":
                prices = {mint: spots[mint]["px"] for mint in idx.get("units", {}) if self._usable(spots.get(mint))}
                level = gindex.level_from_prices(idx, prices)
                if level is None:
                    spot, frozen = rec.get("spot"), True
                else:
                    idx["last_prices"].update(prices)
                    idx["level"] = level
                    spot, frozen = level, False
                    rec["sources"] = {"components": len(prices)}
            else:
                s = spots.get(m["mint"])
                if not self._usable(s):
                    spot, frozen = rec.get("spot"), True
                    if s:
                        rec["last_dev"] = round(s["dev"], 2)
                        rec["sources"] = s["by_source"]
                else:
                    spot, frozen = s["px"] * m["multiplier"], False
                    rec["sources"] = s["by_source"]

            if spot is None:
                continue
            if frozen:
                if "frozen_since" not in rec:
                    rec["frozen_since"] = now
                    state.log_event(
                        "alert",
                        f"{coin}: price frozen (sources disagree or went missing). "
                        f"Auto-halt in {OCFG['auto_halt_after_freeze_sec']}s.",
                    )
                if now - rec["frozen_since"] > OCFG["auto_halt_after_freeze_sec"] and not self.dry_run:
                    halt_market(coin, "oracle frozen: sources disagree or went missing", self.dep)
                    continue
            else:
                if rec.pop("frozen_since", None):
                    state.log_event("oracle", f"{coin}: price updates resumed")
                hist = self.spot_hist.setdefault(coin, deque(maxlen=40))
                hist.append((now, spot))
                old = next((p for t, p in hist if t >= now - 60), None)
                if old and abs(spot / old - 1) * 100 > OCFG["alert_move_pct_per_min"]:
                    state.log_event("alert", f"{coin}: moved {100 * (spot / old - 1):+.0f}% in one minute")

            mark = ema(rec.get("mark"), spot, OCFG["ema_alpha"])
            rec.update({"spot": spot, "mark": mark, "ts": int(now)})
            self.st[coin] = rec
            full = f"{DEX}:{coin}"
            szd = m["sz_decimals"]
            oracle_pxs[full] = format_px(spot, szd)
            mark_pxs[full] = format_px(mark, szd)
            ext_pxs[full] = format_px(spot, szd)

        if idx.get("units"):
            state.save("index", idx)
        state.save("oracle", self.st)
        if not oracle_pxs:
            return
        send = self._should_send()
        if send and not self.dry_run:
            self.dep.set_oracle(oracle_pxs, mark_pxs, ext_pxs)
        tag = "dry-run " if self.dry_run else ("" if send else "standby ")
        print(
            f"[{time.strftime('%H:%M:%S')}] {tag}setOracle  "
            + "  ".join(f"{k} {v}" for k, v in sorted(oracle_pxs.items())),
            flush=True,
        )
        if send:
            state.save("oracle_alive", {"ts": int(now), "assets": len(oracle_pxs), "dry_run": self.dry_run})

    def heartbeat(self) -> None:
        markets = state.load("markets")
        live = [c for c, m in markets.items() if m.get("status") == "live"]
        frozen = [c for c, r in self.st.items() if r.get("frozen_since")]
        lines = [f"Live markets: {len(live)} ({', '.join(live) or 'none'})"]
        for coin in live[:12]:
            r = self.st.get(coin, {})
            if r.get("spot"):
                lines.append(f"{coin}: spot {r['spot']:.5g} / mark {r['mark']:.5g}")
        if frozen:
            lines.append(f"Frozen: {', '.join(frozen)}")
        state.log_event("heartbeat", "\n".join(lines))

    def run(self) -> None:
        interval = max(2.6, float(OCFG["update_interval_sec"]))
        mode = "dry-run" if self.dry_run else ("standby" if self.primary_url else "live")
        state.log_event("oracle", f"Oracle started ({mode}), every {interval}s, sources: {', '.join(self.sources)}")
        errors = 0
        hb_every = CFG.get("telegram", {}).get("heartbeat_hours", 12) * 3600
        last_hb = time.time()
        while True:
            started = time.time()
            if hb_every and started - last_hb >= hb_every:
                last_hb = started
                self.heartbeat()
            try:
                self.tick()
                errors = 0
            except Exception as e:
                errors += 1
                state.log_event("error", f"Oracle tick failed: {e}")
                if errors >= 20:
                    time.sleep(30)
            time.sleep(max(0.0, interval - (time.time() - started)))
