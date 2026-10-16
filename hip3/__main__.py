"""HyperGrad CLI: python -m hip3 <command>

  scan                 find graduates and assign tiers
  index [--force]      recompute the GRAD index composition
  init-dex [--max-gas] create the DEX and list GRAD (requires the 500k HYPE stake)
  list <mint>          list a single perp for a tier1+ coin
  halt <COIN> [reason] halt a market (positions settle at mark)
  resume <COIN>        resume a halted market
  oracle [--dry-run]   run the oracle (every ~3s)
  manager [--once]     run the manager (scan, index, delistings, watchdog)
  serve                dashboard at http://localhost:8787
  status               DEX state as seen by Hyperliquid
  auction              HIP-3 slot auction status
  economics            stake return calculator
  tg-chatid            find your chat_id for Telegram alerts
  tg-test              send a test alert
  watchdog             run the oracle watchdog as its own process
  doctor               preflight checks before init-dex and on every deploy
  mm [--dry-run]       run the market maker
  mm-cancel            pull every market maker order
  backtest <mint>      replay a coin's history through the HIP-3 mark rule
  add-oracle-signer <address> [--revoke]   allow a standby oracle key
  apply-funding        re-apply funding settings from config.json
"""
import argparse
import json
import sys


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="hip3", description="HyperGrad: HIP-3 perps for graduated Solana memecoins")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan", help="find graduates and assign tiers")
    s = sub.add_parser("index", help="recompute the GRAD composition"); s.add_argument("--force", action="store_true")
    s = sub.add_parser("init-dex", help="create the DEX and list GRAD"); s.add_argument("--max-gas", type=int, default=None)
    s = sub.add_parser("list", help="list a single perp"); s.add_argument("mint"); s.add_argument("--max-gas", type=int, default=None); s.add_argument("--force", action="store_true")
    s = sub.add_parser("halt", help="halt a market"); s.add_argument("coin"); s.add_argument("reason", nargs="?", default="manual halt")
    s = sub.add_parser("resume", help="resume a market"); s.add_argument("coin")
    s = sub.add_parser("oracle", help="run the oracle"); s.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("manager", help="run the manager"); s.add_argument("--once", action="store_true")
    s = sub.add_parser("serve", help="run the dashboard"); s.add_argument("--port", type=int, default=None)
    sub.add_parser("status", help="DEX state on Hyperliquid")
    sub.add_parser("auction", help="HIP-3 auction status")
    sub.add_parser("economics", help="stake return calculator")
    sub.add_parser("tg-test", help="send a test Telegram alert")
    sub.add_parser("tg-chatid", help="show chat ids that messaged the bot")
    sub.add_parser("watchdog", help="run the oracle watchdog")
    sub.add_parser("doctor", help="preflight checks")
    s = sub.add_parser("mm", help="run the market maker"); s.add_argument("--dry-run", action="store_true")
    sub.add_parser("mm-cancel", help="pull every market maker order")
    s = sub.add_parser("backtest", help="oracle lag backtest"); s.add_argument("mint")
    s = sub.add_parser("add-oracle-signer", help="allow a standby oracle key"); s.add_argument("address"); s.add_argument("--revoke", action="store_true")
    sub.add_parser("apply-funding", help="re-apply funding settings")
    a = p.parse_args()

    if a.cmd == "scan":
        from .scanner import run_scan
        run_scan()
    elif a.cmd == "index":
        from . import index, state
        idx = index.rebalance(state.load("candidates"), force=a.force)
        for m, w in sorted(idx.get("weights", {}).items(), key=lambda x: -x[1]):
            print(f"{idx['symbols'].get(m, m)[:10]:<12}{w:>7.2%}")
        print(f"Level: {idx.get('level')}")
    elif a.cmd == "init-dex":
        from .listing import init_dex
        init_dex(a.max_gas)
    elif a.cmd == "list":
        from .listing import list_coin
        print("Listed:", list_coin(a.mint, a.max_gas, a.force))
    elif a.cmd == "halt":
        from .listing import halt_market
        halt_market(a.coin, a.reason)
    elif a.cmd == "resume":
        from .listing import resume_market
        resume_market(a.coin)
    elif a.cmd == "oracle":
        from .oracle import Oracle
        Oracle(dry_run=a.dry_run).run()
    elif a.cmd == "manager":
        from . import manager
        manager.run_once() if a.once else manager.run_forever()
    elif a.cmd == "serve":
        from .server import serve
        serve(a.port)
    elif a.cmd == "status":
        from . import hl_client
        from .config import DEX, NETWORK
        print("Network:", NETWORK)
        mine = next((d for d in hl_client.perp_dexs() if d and d.get("name") == DEX), None)
        print(json.dumps(mine or {"info": f"DEX '{DEX}' has not been created yet"}, ensure_ascii=False, indent=2))
        if mine:
            meta, ctxs = hl_client.dex_meta(DEX)
            for asset, ctx in zip(meta["universe"], ctxs):
                print(f"{asset['name']:<16} mark {ctx.get('markPx')}  OI {ctx.get('openInterest')}  vol24h {ctx.get('dayNtlVlm')}")
    elif a.cmd == "auction":
        from . import hl_client
        print(json.dumps(hl_client.auction_status(), ensure_ascii=False, indent=2))
    elif a.cmd == "tg-test":
        from .notify import send_test
        print("Sent." if send_test() else "Failed: check the bot token and chat id.")
    elif a.cmd == "tg-chatid":
        from .notify import get_chat_ids
        chats = get_chat_ids()
        if not chats:
            print("No chats yet. Send any message to your bot (or add it to a group) and run this again.")
        for c in chats:
            print(f"chat_id: {c['chat_id']}   ({c['name']})")
    elif a.cmd == "watchdog":
        from .watchdog import run_forever
        run_forever()
    elif a.cmd == "doctor":
        from .doctor import run
        sys.exit(run())
    elif a.cmd == "mm":
        from .mm import MarketMaker
        MarketMaker(dry_run=a.dry_run).run()
    elif a.cmd == "mm-cancel":
        from .mm import MarketMaker
        MarketMaker().cancel_all()
    elif a.cmd == "backtest":
        from .backtest import run
        run(a.mint)
    elif a.cmd == "add-oracle-signer":
        from .listing import add_oracle_signer
        add_oracle_signer(a.address, not a.revoke)
    elif a.cmd == "apply-funding":
        from .listing import apply_funding
        apply_funding()
    elif a.cmd == "economics":
        import runpy
        from .config import ROOT
        runpy.run_path(str(ROOT / "economics" / "model.py"), run_name="__main__")


if __name__ == "__main__":
    main()
