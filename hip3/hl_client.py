"""Hyperliquid client: info reads and signed HIP-3 deployer actions (perpDeploy).

Signing goes through the official hyperliquid-python-sdk. Field order inside actions
matters (the action is msgpack-hashed), so it mirrors the HIP-3 deployer actions docs.
"""
from .config import API_URL, DEX, NETWORK, env
from .http import post_json


def info(payload: dict):
    return post_json(f"{API_URL}/info", payload)


def perp_dexs():
    return info({"type": "perpDexs"})


def dex_meta(dex: str = DEX):
    """[meta, assetCtxs] for our DEX."""
    return info({"type": "metaAndAssetCtxs", "dex": dex})


def auction_status():
    return info({"type": "perpDeployAuctionStatus"})


def _sorted(pairs):
    return sorted(pairs, key=lambda p: p[0])


class Deployer:
    """Sends perpDeploy actions from the deployer wallet (or the oracle updater wallet)."""

    def __init__(self, key_env: str = "HL_PRIVATE_KEY"):
        from eth_account import Account
        from hyperliquid.exchange import Exchange
        from hyperliquid.utils import constants

        key = env(key_env) or env("HL_PRIVATE_KEY")
        if not key:
            raise SystemExit(f"Missing private key: set {key_env} in .env")
        if NETWORK == "mainnet" and env("HL_ALLOW_MAINNET") != "yes":
            raise SystemExit("Mainnet is locked. Set HL_ALLOW_MAINNET=yes in .env to proceed.")
        self.wallet = Account.from_key(key)
        base = constants.MAINNET_API_URL if NETWORK == "mainnet" else constants.TESTNET_API_URL
        self.ex = Exchange(self.wallet, base, account_address=env("HL_ACCOUNT_ADDRESS"))
        self.is_mainnet = NETWORK == "mainnet"

    @property
    def address(self) -> str:
        return env("HL_ACCOUNT_ADDRESS") or self.wallet.address

    def _send(self, action: dict):
        from hyperliquid.utils.signing import get_timestamp_ms, sign_l1_action

        nonce = get_timestamp_ms()
        try:
            sig = sign_l1_action(
                self.ex.wallet, action, None, nonce, getattr(self.ex, "expires_after", None), self.is_mainnet
            )
        except TypeError:  # older SDK versions without expires_after
            sig = sign_l1_action(self.ex.wallet, action, None, nonce, self.is_mainnet)
        res = self.ex._post_action(action, sig, nonce)
        if isinstance(res, dict) and res.get("status") == "err":
            raise RuntimeError(f"Hyperliquid rejected {list(action)[-1]}: {res.get('response')}")
        return res

    def perp_deploy(self, variant: str, payload):
        return self._send({"type": "perpDeploy", variant: payload})

    # --- Listing ---------------------------------------------------------
    def register_asset(self, coin, sz_decimals, oracle_px, margin_table_id, max_gas, schema):
        if hasattr(self.ex, "perp_deploy_register_asset"):
            return self.ex.perp_deploy_register_asset(
                DEX, max_gas, coin, sz_decimals, oracle_px, margin_table_id, True, schema
            )
        payload = {
            "maxGas": max_gas,
            "assetRequest": {
                "coin": coin,
                "szDecimals": sz_decimals,
                "oraclePx": oracle_px,
                "marginTableId": margin_table_id,
                "onlyIsolated": True,
            },
            "dex": DEX,
            "schema": schema,
        }
        return self.perp_deploy("registerAsset", payload)

    # --- Oracle ----------------------------------------------------------
    def set_oracle(self, oracle_pxs: dict[str, str], mark_pxs: dict[str, str], external_pxs: dict[str, str]):
        if hasattr(self.ex, "perp_deploy_set_oracle"):
            try:
                return self.ex.perp_deploy_set_oracle(DEX, oracle_pxs, [mark_pxs], external_pxs)
            except TypeError:  # SDK versions without externalPerpPxs
                pass
        payload = {
            "dex": DEX,
            "oraclePxs": _sorted(list(oracle_pxs.items())),
            "markPxs": [_sorted(list(mark_pxs.items()))],
            "externalPerpPxs": _sorted(list(external_pxs.items())),
        }
        return self.perp_deploy("setOracle", payload)

    # --- Market management -------------------------------------------------
    def halt(self, coin: str, halted: bool = True):
        return self.perp_deploy("haltTrading", {"coin": f"{DEX}:{coin}", "isHalted": halted})

    def set_oi_caps(self, caps: dict[str, int | None]):
        return self.perp_deploy("setOpenInterestCaps", _sorted([[f"{DEX}:{c}", v] for c, v in caps.items()]))

    def set_margin_modes(self, modes: dict[str, str]):
        return self.perp_deploy("setMarginModes", _sorted([[f"{DEX}:{c}", m] for c, m in modes.items()]))

    def set_margin_table_ids(self, ids: dict[str, int]):
        return self.perp_deploy("setMarginTableIds", _sorted([[f"{DEX}:{c}", i] for c, i in ids.items()]))

    def set_deployer_fees(self, coin: str, scale: str, growth_mode: bool):
        return self.perp_deploy("setDeployerFees", [[f"{DEX}:{coin}", {"scale": scale, "growthMode": growth_mode}]])

    def set_fee_recipient(self, recipient: str):
        return self.perp_deploy("setFeeRecipient", {"dex": DEX, "feeRecipient": recipient})

    def set_funding_multipliers(self, mults: dict[str, str]):
        return self.perp_deploy("setFundingMultipliers", _sorted([[f"{DEX}:{c}", m] for c, m in mults.items()]))

    def set_funding_clamps(self, clamps: dict[str, str]):
        return self.perp_deploy("setFundingClamps", _sorted([[f"{DEX}:{c}", v] for c, v in clamps.items()]))

    def set_sub_deployer(self, variant: str, user: str, allowed: bool = True):
        return self.perp_deploy(
            "setSubDeployers", {"dex": DEX, "subDeployers": [{"variant": variant, "user": user, "allowed": allowed}]}
        )

    def annotate(self, coin: str, category: str, description: str, display_name: str | None, keywords: list[str]):
        return self.perp_deploy(
            "setPerpAnnotation",
            {
                "coin": f"{DEX}:{coin}",
                "category": category[:15],
                "description": description[:400],
                "displayName": display_name[:9] if display_name else None,
                "keywords": [k[:10] for k in keywords[:2]],
            },
        )
