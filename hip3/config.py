"""Loads config.json and .env."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
STATE_DIR.mkdir(exist_ok=True)


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def load_config() -> dict:
    with open(ROOT / "config.json", encoding="utf-8") as f:
        return json.load(f)


CFG = load_config()


def env(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    return val if val not in (None, "") else default


NETWORK = (env("HL_NETWORK", "testnet") or "testnet").lower()
API_URL = (
    "https://api.hyperliquid.xyz" if NETWORK == "mainnet" else "https://api.hyperliquid-testnet.xyz"
)
DEX = CFG["dex"]["code"]
