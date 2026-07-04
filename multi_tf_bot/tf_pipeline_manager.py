"""
TF Pipeline Manager
Manages 7 independent STLMSPipeline instances (File #33).
Each TF runs analysis up to Intelligence Layer only.
No trade execution happens here.
"""
import logging
from decimal import Decimal
from typing import Dict, Optional, List
from datetime import datetime, timezone

from st_lms_core.core.models.candle import Candle
from st_lms_core.core.pipeline.orchestrator import STLMSPipeline
from multi_tf_bot.models import TFAnalysisSnapshot, STLineRecord, WaveRecord

logger = logging.getLogger(__name__)


class TFPipelineManager:
    """
    Manages one STLMSPipeline instance per timeframe.
    Extracts complete analysis state after each candle.
    """

    def __init__(self, timeframes: List[str]):
        self.timeframes = timeframes
        self.pipelines: Dict[str, STLMSPipeline] = {}
        self.snapshots: Dict[str, TFAnalysisSnapshot] = {}
        self._candle_counts: Dict[str, int] = {tf: 0 for tf in timeframes}

        for tf in timeframes:
            self.pipelines[tf] = STLMSPipeline()
            self.snapshots[tf] = TFAnalysisSnapshot(timeframe=tf, timestamp=0, price=0.0)
            logger.info(f"[PIPE-MGR] Initialized pipeline for {tf}")

    def process_candle(self, timeframe: str, candle_data: dict) -> Optional[TFAnalysisSnapshot]:
        """Process a closed candle through the appropriate TF pipeline."""
        if timeframe not in self.pipelines:
            logger.warning(f"[PIPE-MGR] Unknown timeframe: {timeframe}")
            return None

        pipeline = self.pipelines[timeframe]

        candle = Candle(
            timestamp=candle_data["timestamp"],
            open=candle_data["open"],
            high=candle_data["high"],
            low=candle_data["low"],
            close=candle_data["close"],
            st_point=Decimal("0"),
            macd_value=Decimal("0"),
            oi_value=None,
        )

        audit = pipeline.process_candle(candle)

        if audit is None:
            return None

        self._candle_counts[timeframe] += 1

        snapshot = self._extract_snapshot(timeframe, pipeline, audit, candle_data)
        self.snapshots[timeframe] = snapshot

        if self._candle_counts[timeframe] % 50 == 0:
            logger.info(
                f"[PIPE-MGR] {timeframe} | #{self._candle_counts[timeframe]} | "
                f"Price={snapshot.price:.2f} | Trend={snapshot.trend_state} | "
                f"Lines={len(snapshot.st_lines)} | Waves={1 if snapshot.last_wave else 0}"
            )

        return snapshot

    def _extract_snapshot(
        self, tf: str, pipeline: STLMSPipeline, audit: dict, candle_data: dict
    ) -> TFAnalysisSnapshot:
        """Extract all analysis outputs from pipeline internal state."""
        context = getattr(pipeline, '_last_context', None)
        tag = getattr(pipeline, '_last_tag', None)
        active_ctx = getattr(pipeline, '_last_active_context', None)
        fib = getattr(pipeline, '_last_fib', None)
        line_builder = getattr(pipeline, '_line_builder', None)
        wave_builder = getattr(pipeline, '_wave_builder', None)

        st_lines = []
        if line_builder:
            for line in line_builder.all_lines:
                st_lines.append(STLineRecord(
                    id=line.id,
                    price=float(line.price_level),
                    direction=line.direction.value,
                    status=line.status.value,
                    point_count=line.point_count,
                    start_ts=line.start_ts,
                    end_ts=line.end_ts,
                    timeframe=tf,
                ))

        last_wave = None
        if wave_builder and wave_builder.last_completed_wave:
            w = wave_builder.last_completed_wave
            last_wave = WaveRecord(
                id=w.id,
                direction=w.direction.value,
                start_price=float(w.start_price),
                end_price=float(w.end_price),
                amplitude=float(w.amplitude),
                length_points=w.length_points,
                start_ts=w.start_ts,
                end_ts=w.end_ts,
                timeframe=tf,
            )

        fib_levels = None
        if fib:
            fib_levels = {
                "000": float(fib.level_000),
                "236": float(fib.level_236),
                "382": float(fib.level_382),
                "500": float(fib.level_500),
                "618": float(fib.level_618),
                "786": float(fib.level_786),
                "100": float(fib.level_100),
            }

        return TFAnalysisSnapshot(
            timeframe=tf,
            timestamp=candle_data["timestamp"],
            price=float(candle_data["close"]),
            st_point=audit.get("st_point"),
            st_lines=st_lines,
            last_wave=last_wave,
            fib_levels=fib_levels,
            macd_bucket=audit.get("macd", "NEUTRAL"),
            oi_state=audit.get("oi", "ABSENT"),
            velocity=audit.get("velocity", "NORMAL_FLOW"),
            trend_state=audit.get("trend", "SIDEWAY"),
            structural_form=audit.get("form", "NO_STRUCTURE"),
            stack_priority=audit.get("stack_priority", "LOW"),
            compressed=audit.get("compressed", False),
            wave_direction=audit.get("wave_direction"),
            wave_length=audit.get("wave_length", 0),
            nearest_support=float(active_ctx.nearest_support.price_level) if active_ctx and active_ctx.nearest_support else None,
            nearest_resistance=float(active_ctx.nearest_resistance.price_level) if active_ctx and active_ctx.nearest_resistance else None,
            candle_count=self._candle_counts[tf],
        )

    def get_all_snapshots(self) -> Dict[str, TFAnalysisSnapshot]:
        return dict(self.snapshots)

    def get_st_lines_all_tf(self) -> Dict[str, List[STLineRecord]]:
        """Get all active ST lines across all timeframes."""
        result = {}
        for tf, snap in self.snapshots.items():
            result[tf] = [l for l in snap.st_lines if l.is_active]
        return result

    def is_warmup_complete(self, timeframe: str) -> bool:
        if timeframe not in self.pipelines:
            return False
        return self.pipelines[timeframe].is_warmup_complete

    def reset(self):
        for tf in self.timeframes:
            self.pipelines[tf].reset()
            self.snapshots[tf] = TFAnalysisSnapshot(timeframe=tf, timestamp=0, price=0.0)
            self._candle_counts[tf] = 0
