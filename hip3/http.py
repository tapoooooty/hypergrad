"""Minimal HTTP client with retries (requests)."""
import time

import requests

_session = requests.Session()
_session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) hypergrad/1.1",
        "Accept": "application/json",
    }
)


def get_json(url: str, params: dict | None = None, retries: int = 3, timeout: float = 10.0):
    last = None
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, timeout=timeout)
            if r.status_code == 429:
                time.sleep(2 + attempt * 3)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            last = e
            time.sleep(1 + attempt)
    raise RuntimeError(f"GET {url} failed: {last}")


def post_json(url: str, payload: dict, retries: int = 3, timeout: float = 10.0):
    last = None
    for attempt in range(retries):
        try:
            r = _session.post(url, json=payload, timeout=timeout)
            if r.status_code == 429:
                time.sleep(2 + attempt * 3)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            last = e
            time.sleep(1 + attempt)
    raise RuntimeError(f"POST {url} failed: {last}")
