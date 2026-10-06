"""Project state stored as JSON files (atomic writes)."""
import json
import os
import threading
import time
from pathlib import Path

from .config import STATE_DIR

_lock = threading.Lock()


def _path(name: str) -> Path:
    return STATE_DIR / f"{name}.json"


def load(name: str, default=None):
    p = _path(name)
    if not p.exists():
        return {} if default is None else default
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {} if default is None else default


def save(name: str, data) -> None:
    p = _path(name)
    tmp = p.with_suffix(f".{os.getpid()}.tmp")
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)


def log_event(kind: str, message: str, **extra) -> None:
    """Event log for the dashboard (last 500) + Telegram alerts."""
    events = load("events", default=[])
    events.append({"ts": int(time.time()), "kind": kind, "message": message, **extra})
    save("events", events[-500:])
    print(f"[{time.strftime('%H:%M:%S')}] {kind.upper()}: {message}", flush=True)
    try:
        from .notify import notify

        notify(kind, message)
    except Exception:
        pass


# State files:
# candidates.json   : {mint: {...metrics, tier, history: [[ts, mcap, liq]]}}
# markets.json      : {"GRAD": {...}, "MWIF": {"mint", "multiplier", "sz_decimals", "status": "live|halted"}}
# index.json        : {"level", "units": {mint: u}, "last_prices": {mint: p}, "rebalanced_at"}
# oracle.json       : {coin: {"spot", "mark", "ts", "frozen_since"}}
# oracle_alive.json : {"ts": last successful setOracle}
