"""Oracle watchdog: alerts on Telegram when no setOracle has gone out while markets are live.

Runs as a background thread inside the manager (or standalone: python -m hip3 watchdog).
It lives in a different process from the oracle, so it notices when the oracle dies entirely.
"""
import threading
import time

from . import state
from .config import CFG

TCFG = CFG.get("telegram", {})


def check_once(was_down: bool) -> bool:
    markets = state.load("markets")
    if not any(m.get("status") == "live" for m in markets.values()):
        return False
    age = time.time() - state.load("oracle_alive").get("ts", 0)
    if age > TCFG.get("watchdog_stale_sec", 30):
        state.log_event(
            "watchdog",
            f"Oracle silent for {int(age // 60)}m {int(age % 60)}s. After 10s without updates the mark "
            "falls back to the local price; long downtime risks slashing. Check the oracle host.",
        )
        return True
    if was_down:
        state.log_event("watchdog", "Oracle is publishing prices again")
    return False


def run_forever(interval: float = 15.0) -> None:
    down = False
    while True:
        try:
            down = check_once(down)
        except Exception as e:
            print("watchdog:", e)
        time.sleep(interval)


def start_thread() -> None:
    threading.Thread(target=run_forever, daemon=True, name="watchdog").start()
