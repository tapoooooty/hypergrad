"""Dashboard at http://localhost:8787: graduates feed, markets, oracle, index and events."""
import json
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from . import hl_client, state
from .config import CFG, DEX, NETWORK, ROOT, env

_cache = {"ts": 0, "data": None}


def _live_meta():
    if time.time() - _cache["ts"] < 10:
        return _cache["data"]
    try:
        meta, ctxs = hl_client.dex_meta(DEX)
        data = [
            {
                "name": asset.get("name"),
                "maxLeverage": asset.get("maxLeverage"),
                "markPx": ctx.get("markPx"),
                "oraclePx": ctx.get("oraclePx"),
                "openInterest": ctx.get("openInterest"),
                "dayNtlVlm": ctx.get("dayNtlVlm"),
                "funding": ctx.get("funding"),
            }
            for asset, ctx in zip(meta.get("universe", []), ctxs)
        ]
    except Exception as e:
        data = {"error": str(e)[:200]}
    _cache.update(ts=time.time(), data=data)
    return data


def snapshot() -> dict:
    keys = (
        "mint", "symbol", "name", "price_usd", "mcap_usd", "liquidity_usd", "volume_24h_usd",
        "price_change_1h_pct", "created_ms", "tier", "next_tier_blockers", "top10_pct", "dev_pct", "url",
    )
    slim = [
        {k: c.get(k) for k in keys} | {"spark": [h[1] for h in c.get("history", [])[-48:]]}
        for c in state.load("candidates").values()
    ]
    slim.sort(key=lambda c: c.get("mcap_usd") or 0, reverse=True)
    return {
        "network": NETWORK,
        "dex": DEX,
        "tiers": CFG["tiers"],
        "candidates": slim,
        "markets": state.load("markets"),
        "index": state.load("index"),
        "oracle": state.load("oracle"),
        "oracle_alive": state.load("oracle_alive"),
        "events": state.load("events", default=[])[-120:][::-1],
        "live": _live_meta(),
        "server_ts": int(time.time()),
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT / "web"), **kw)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/api/health"):
            ts = state.load("oracle_alive").get("ts")
            body = json.dumps({"oracle_age": int(time.time() - ts) if ts else None, "network": NETWORK, "dex": DEX}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/api/state"):
            body = json.dumps(snapshot(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def serve(port: int | None = None) -> None:
    port = port or CFG["dashboard"]["port"]
    host = env("DASHBOARD_HOST") or CFG["dashboard"].get("host", "127.0.0.1")
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"HyperGrad dashboard: http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}  (Ctrl+C to stop)")
    httpd.serve_forever()
