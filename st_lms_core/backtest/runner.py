"""
Backtest Runner - Executes Adaptive Pipeline on Historical Data.
Supports 5m native klines + OI exact-match.
Dual timestamp (UTC + WIB) in output CSV.
Account balance passed to pipeline (Audit Fix #3).
"""
import json, csv, logging
from decimal import Decimal
from typing import List, Dict

from st_lms_core.core.models.candle import Candle
from st_lms_core.core.pipeline.adaptive_orchestrator import AdaptiveSTLMSPipeline
from st_lms_core.core.data.oi_merger import OIMerger
from st_lms_core.core.data.validator import DataValidator
from st_lms_core.utils.datetime import format_dual_ts

logger = logging.getLogger(__name__)


class BacktestRunner:
    def __init__(self):
        pass

    def load_klines(self, filepath: str) -> List[Candle]:
        with open(filepath, "r") as f:
            raw = json.load(f)
        candles = []
        for k in raw:
            candles.append(Candle(
                timestamp=int(k[0]),
                open=Decimal(str(k[1]).strip()), high=Decimal(str(k[2]).strip()),
                low=Decimal(str(k[3]).strip()), close=Decimal(str(k[4]).strip()),
                st_point=Decimal("0"), macd_value=Decimal("0"), oi_value=None
            ))
        return candles

    def load_oi(self, filepath: str) -> List[Dict]:
        with open(filepath, "r") as f:
            raw = json.load(f)
        return OIMerger.clean_raw_oi(raw)

    def run(self, klines_path: str, oi_path: str,
            account_balance: Decimal = Decimal("10000"),
            mode: str = "LONG_ONLY",
            output_csv: str = "backtest_results.csv") -> dict:
        logger.info(f"[BACKTEST] Loading klines from {klines_path}")
        candles = self.load_klines(klines_path)
        logger.info(f"[BACKTEST] Loaded {len(candles)} candles")

        klines_valid, klines_warnings = DataValidator.validate_klines(candles)
        if not klines_valid:
            logger.error("[BACKTEST] Kline validation FAILED. Aborting.")
            return {"error": "KLINE_VALIDATION_FAILED", "warnings": klines_warnings}

        logger.info(f"[BACKTEST] Loading OI from {oi_path}")
        oi_records = self.load_oi(oi_path)
        oi_records, dedup_warnings = DataValidator.deduplicate_oi(oi_records)
        oi_valid, oi_warnings = DataValidator.validate_oi(oi_records)
        if not oi_valid:
            logger.warning("[BACKTEST] OI validation has issues, continuing with cleaned data")

        candles = OIMerger.merge(candles, oi_records)
        matched = sum(1 for c in candles if c.has_oi)
        logger.info(f"[BACKTEST] OI matched: {matched}/{len(candles)} ({matched*100//max(len(candles),1)}%)")

        pipeline = AdaptiveSTLMSPipeline(account_balance=account_balance, allowed_modes=[mode])

        audits = []
        entries = 0
        exits = 0
        for candle in candles:
            audit = pipeline.process_candle(candle)
            if audit:
                dual_ts = format_dual_ts(candle.timestamp)
                audit["time_utc"] = dual_ts["utc"]
                audit["time_wib"] = dual_ts["wib"]
                audit["open"] = float(candle.open)
                audit["high"] = float(candle.high)
                audit["low"] = float(candle.low)
                audit["close"] = float(candle.close)
                audits.append(audit)
                if audit.get("entry"):
                    entries += 1
                if audit.get("exit"):
                    exits += 1

        if audits:
            with open(output_csv, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=audits[0].keys())
                writer.writeheader()
                writer.writerows(audits)
            logger.info(f"[BACKTEST] Results exported: {output_csv}")

        summary = pipeline.get_learning_summary()
        summary.update({
            "total_candles": len(candles), "processed_candles": len(audits),
            "entries_triggered": entries, "exits_triggered": exits,
            "oi_matched": matched,
            "oi_coverage_pct": round(matched * 100 / max(len(candles), 1), 1),
            "account_balance": float(account_balance), "mode": mode
        })

        logger.info("=" * 60)
        logger.info("  BACKTEST COMPLETE")
        logger.info("=" * 60)
        logger.info(f"  Candles:       {summary['processed_candles']}")
        logger.info(f"  Entries:       {entries}")
        logger.info(f"  Exits:         {exits}")
        logger.info(f"  OI Coverage:   {summary['oi_coverage_pct']}%")
        logger.info(f"  River Records: {summary['entry_records']}")
        logger.info(f"  Patterns:      {summary['unique_entry_patterns']}")
        logger.info("=" * 60)

        return summary
