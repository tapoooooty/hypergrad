"""Telegram alerts.

Setup: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env, rules in the telegram section of config.json.
Messages are sent from a background thread and never block the oracle.
Identical messages are suppressed for dedup_sec.
"""
import queue
import threading
import time

import requests

from .config import CFG, DEX, NETWORK, env

TCFG = CFG.get("telegram", {})
TOKEN = env("TELEGRAM_BOT_TOKEN")
CHAT_IDS = [c.strip() for c in (env("TELEGRAM_CHAT_ID") or "").split(",") if c.strip()]

ICONS = {
    "alert": "⚠️", "halt": "⛔", "error": "🔥", "listing": "🚀", "candidate": "🎯", "tier": "📈",
    "index": "🧺", "oracle": "🔮", "manager": "🛠", "delist?": "🪦", "warn": "🟡",
    "watchdog": "🐕", "heartbeat": "💚", "mm": "💱",
}

_q: "queue.Queue[str]" = queue.Queue(maxsize=500)
_last_sent: dict[str, float] = {}
_worker_started = False
_lock = threading.Lock()


def enabled() -> bool:
    return bool(TOKEN and CHAT_IDS and TCFG.get("enabled", True))


def _send_now(text: str) -> bool:
    ok = True
    for chat in CHAT_IDS:
        sent = False
        for attempt in range(3):
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                    json={"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
                    timeout=10,
                )
                if r.status_code == 429:
                    time.sleep(float(r.json().get("parameters", {}).get("retry_after", 3)))
                    continue
                sent = r.ok
                break
            except requests.RequestException:
                time.sleep(2 * (attempt + 1))
        ok = ok and sent
    return ok


def _worker() -> None:
    while True:
        text = _q.get()
        try:
            _send_now(text)
        finally:
            _q.task_done()
        time.sleep(0.05)


def flush(timeout: float = 10.0) -> None:
    """Wait for queued messages (for short CLI commands such as halt)."""
    deadline = time.time() + timeout
    while _q.unfinished_tasks and time.time() < deadline:
        time.sleep(0.1)


def _ensure_worker() -> None:
    global _worker_started
    with _lock:
        if not _worker_started:
            import atexit

            threading.Thread(target=_worker, daemon=True, name="telegram").start()
            atexit.register(flush)
            _worker_started = True


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_message(kind: str, message: str) -> str:
    icon = ICONS.get(kind, "•")
    net = "MAINNET" if NETWORK == "mainnet" else "testnet"
    return f"{icon} <b>{_escape(kind.capitalize())}</b> on <code>{DEX}</code> ({net})\n{_escape(message)}"


def notify(kind: str, message: str, force: bool = False) -> None:
    """Queue an alert if this event kind is enabled in config.json."""
    if not enabled():
        return
    if not force and kind not in TCFG.get("kinds", []):
        return
    key = f"{kind}:{message}"
    now = time.time()
    if not force and now - _last_sent.get(key, 0) < TCFG.get("dedup_sec", 300):
        return
    _last_sent[key] = now
    _ensure_worker()
    try:
        _q.put_nowait(format_message(kind, message))
    except queue.Full:
        pass


def send_test() -> bool:
    if not (TOKEN and CHAT_IDS):
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
    return _send_now(format_message("oracle", "Test message: HyperGrad alerts are connected."))


def get_chat_ids() -> list[dict]:
    """Helper: message your bot once, then call this to see your chat_id."""
    if not TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env")
    r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", timeout=10).json()
    seen = {}
    for upd in r.get("result", []):
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") is not None:
            seen[chat["id"]] = chat.get("title") or chat.get("username") or chat.get("first_name")
    return [{"chat_id": k, "name": v} for k, v in seen.items()]
