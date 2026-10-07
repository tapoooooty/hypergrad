"""Solana JSON-RPC: holder concentration and dev wallet share."""
from ..http import post_json


class SolanaRPC:
    def __init__(self, url: str):
        self.url = url
        self._id = 0

    def call(self, method: str, params: list):
        self._id += 1
        res = post_json(self.url, {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        if "error" in res:
            raise RuntimeError(res["error"])
        return res["result"]

    def supply(self, mint: str) -> float:
        r = self.call("getTokenSupply", [mint])
        return float(r["value"]["uiAmount"] or 0)

    def top10_pct(self, mint: str) -> float:
        """Share of the top-10 token accounts, excluding the largest one (usually the liquidity pool)."""
        total = self.supply(mint)
        if total <= 0:
            return 100.0
        r = self.call("getTokenLargestAccounts", [mint])
        amounts = sorted((float(a.get("uiAmount") or 0) for a in r["value"]), reverse=True)
        return 100.0 * sum(amounts[1:11]) / total

    def wallet_pct(self, owner: str, mint: str) -> float:
        total = self.supply(mint)
        if total <= 0:
            return 0.0
        r = self.call("getTokenAccountsByOwner", [owner, {"mint": mint}, {"encoding": "jsonParsed"}])
        amt = 0.0
        for acc in r.get("value", []):
            info = acc["account"]["data"]["parsed"]["info"]
            amt += float(info["tokenAmount"]["uiAmount"] or 0)
        return 100.0 * amt / total
