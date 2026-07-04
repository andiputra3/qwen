#!/usr/bin/env python3
"""
Multi-TF Confluence Bot - Phase 3 Final Entry Point
Usage:
  python run_multi_tf_bot.py
  python run_multi_tf_bot.py --symbol ETHUSDT --mode SHORT_ONLY
  python run_multi_tf_bot.py --config custom.json --no-dashboard
"""
import asyncio
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)


async def main():
    parser = argparse.ArgumentParser(description="Multi-TF Confluence Bot - Phase 3")
    parser.add_argument("--config", default="multi_tf_bot/config.json")
    parser.add_argument("--symbol", type=str)
    parser.add_argument("--mode", choices=["LONG_ONLY", "SHORT_ONLY", "BOTH"])
    parser.add_argument("--no-dashboard", action="store_true")
    args = parser.parse_args()

    from multi_tf_bot.multi_tf_orchestrator import MultiTFOrchestrator
    orch = MultiTFOrchestrator(args.config)

    if args.symbol:
        orch.symbol = args.symbol
    if args.mode:
        orch.config["mode"] = args.mode
    if args.no_dashboard:
        orch.config["dashboard_enabled"] = False

    try:
        await orch.start()
    except KeyboardInterrupt:
        orch.stop()


if __name__ == "__main__":
    asyncio.run(main())
