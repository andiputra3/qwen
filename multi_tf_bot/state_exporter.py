"""
State Exporter - POST-AUDIT FIXED VERSION
Fix #1: Batch export with throttle (max 1 flush per second)
Fix #2: Thread-safe event log with threading.Lock
Fix #5: History rotation (keep last N files per TF)
Fix #6: Deduplicate export triggers via flush lock
"""
import json
import logging
import threading
import time
from pathlib import Path
from typing import Dict, List
from datetime import datetime, timezone

from multi_tf_bot.models import TFAnalysisSnapshot, MultiTFState

logger = logging.getLogger(__name__)


class StateExporter:
    MAX_HISTORY_PER_TF = 2000
    MIN_FLUSH_INTERVAL_SEC = 1.0

    def __init__(self, output_dir: str = "data/multi_tf_state", symbol: str = "BTCUSDT"):
        self.output_dir = Path(output_dir)
        self.symbol = symbol.lower()
        self.tf_dir = self.output_dir / "timeframes"
        self.history_dir = self.output_dir / "history"
        self.events_file = self.output_dir / "events.jsonl"
        self.global_file = self.output_dir / "global_state.json"
        self.lines_dir = self.output_dir / "st_lines"

        for d in [self.tf_dir, self.history_dir, self.lines_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self._prev_snapshots: Dict[str, TFAnalysisSnapshot] = {}
        self._pending_events: List[dict] = []
        self._event_lock = threading.Lock()
        self._flush_lock = threading.Lock()
        self._last_flush_time: float = 0.0

        logger.info(f"[EXPORTER] Initialized at {self.output_dir}")

    def export_tf_snapshot(self, snapshot: TFAnalysisSnapshot):
        tf = snapshot.timeframe

        latest_path = self.tf_dir / f"{tf}.json"
        with open(latest_path, "w") as f:
            json.dump(self._snapshot_to_dict(snapshot), f, indent=2, default=str)

        prev = self._prev_snapshots.get(tf)
        if prev:
            events = self._diff_snapshots(prev, snapshot, tf)
            if events:
                with self._event_lock:
                    self._pending_events.extend(events)

        self._prev_snapshots[tf] = snapshot
        self._try_flush()

    def _try_flush(self):
        now = time.monotonic()
        with self._flush_lock:
            if now - self._last_flush_time < self.MIN_FLUSH_INTERVAL_SEC:
                return
            self._last_flush_time = now

        with self._event_lock:
            batch = list(self._pending_events)
            self._pending_events.clear()

        if batch:
            with open(self.events_file, "a") as f:
                for evt in batch:
                    f.write(json.dumps(evt, default=str) + "\n")

        for tf, snap in self._prev_snapshots.items():
            self._write_history_with_rotation(tf, snap)

    def _write_history_with_rotation(self, tf: str, snap: TFAnalysisSnapshot):
        ts_str = datetime.fromtimestamp(
            snap.timestamp / 1000, tz=timezone.utc
        ).strftime("%Y%m%d_%H%M%S")
        tf_hist_dir = self.history_dir / tf
        tf_hist_dir.mkdir(parents=True, exist_ok=True)

        hist_path = tf_hist_dir / f"{ts_str}.json"
        with open(hist_path, "w") as f:
            json.dump(self._snapshot_to_dict(snap), f, indent=2, default=str)

        existing = sorted(tf_hist_dir.glob("*.json"))
        if len(existing) > self.MAX_HISTORY_PER_TF:
            to_remove = existing[:len(existing) - self.MAX_HISTORY_PER_TF]
            for old_file in to_remove:
                try:
                    old_file.unlink()
                except OSError:
                    pass

    def _diff_snapshots(self, prev: TFAnalysisSnapshot, curr: TFAnalysisSnapshot, tf: str) -> List[dict]:
        events = []
        ts = curr.timestamp

        if prev.trend_state != curr.trend_state:
            events.append({"ts": ts, "event": "TREND_CHANGED", "object": "Trend",
                           "id": f"TREND_{tf}", "tf": tf,
                           "data": {"from": prev.trend_state, "to": curr.trend_state}})

        if prev.structural_form != curr.structural_form:
            events.append({"ts": ts, "event": "FORM_CHANGED", "object": "Structure",
                           "id": f"FORM_{tf}", "tf": tf,
                           "data": {"from": prev.structural_form, "to": curr.structural_form}})

        prev_ids = {l.id for l in prev.st_lines if l.is_active}
        curr_ids = {l.id for l in curr.st_lines if l.is_active}

        for line in curr.st_lines:
            if line.is_active and line.id not in prev_ids:
                events.append({"ts": ts, "event": "ST_LINE_CREATED", "object": "SupertrendLine",
                               "id": line.id, "tf": tf,
                               "data": {"price": line.price, "direction": line.direction, "status": line.status}})

        for line in prev.st_lines:
            if line.is_active and line.id not in curr_ids:
                events.append({"ts": ts, "event": "ST_LINE_CLOSED", "object": "SupertrendLine",
                               "id": line.id, "tf": tf,
                               "data": {"price": line.price, "direction": line.direction}})

        if curr.last_wave and (not prev.last_wave or curr.last_wave.id != prev.last_wave.id):
            events.append({"ts": ts, "event": "WAVE_COMPLETED", "object": "Wave",
                           "id": curr.last_wave.id, "tf": tf,
                           "data": {"direction": curr.last_wave.direction,
                                    "amplitude": curr.last_wave.amplitude,
                                    "length": curr.last_wave.length_points,
                                    "start_price": curr.last_wave.start_price,
                                    "end_price": curr.last_wave.end_price}})

        if prev.stack_priority != curr.stack_priority:
            events.append({"ts": ts, "event": "STACK_PRIORITY_CHANGED", "object": "AdaptiveStack",
                           "id": f"STACK_{tf}", "tf": tf,
                           "data": {"from": prev.stack_priority, "to": curr.stack_priority}})

        if prev.macd_bucket != curr.macd_bucket:
            events.append({"ts": ts, "event": "MACD_CHANGED", "object": "Measurement",
                           "id": f"MACD_{tf}", "tf": tf,
                           "data": {"from": prev.macd_bucket, "to": curr.macd_bucket}})

        return events

    def _snapshot_to_dict(self, snap: TFAnalysisSnapshot) -> dict:
        return {
            "timeframe": snap.timeframe, "timestamp": snap.timestamp,
            "datetime_utc": datetime.fromtimestamp(snap.timestamp / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "price": snap.price, "st_point": snap.st_point,
            "trend_state": snap.trend_state, "structural_form": snap.structural_form,
            "macd_bucket": snap.macd_bucket, "oi_state": snap.oi_state,
            "velocity": snap.velocity, "stack_priority": snap.stack_priority,
            "compressed": snap.compressed, "wave_direction": snap.wave_direction,
            "wave_length": snap.wave_length,
            "nearest_support": snap.nearest_support, "nearest_resistance": snap.nearest_resistance,
            "candle_count": snap.candle_count, "fib_levels": snap.fib_levels,
            "last_wave": {
                "id": snap.last_wave.id, "direction": snap.last_wave.direction,
                "start_price": snap.last_wave.start_price, "end_price": snap.last_wave.end_price,
                "amplitude": snap.last_wave.amplitude, "length_points": snap.last_wave.length_points,
                "start_line_id": getattr(snap.last_wave, 'start_line_id', None),
                "end_line_id": getattr(snap.last_wave, 'end_line_id', None),
            } if snap.last_wave else None,
            "active_st_lines": [
                {"id": l.id, "price": l.price, "direction": l.direction,
                 "status": l.status, "point_count": l.point_count,
                 "start_ts": l.start_ts, "end_ts": l.end_ts}
                for l in snap.st_lines if l.is_active
            ],
            "all_st_lines_count": len(snap.st_lines),
            "active_st_lines_count": len([l for l in snap.st_lines if l.is_active]),
            "valid_st_lines_count": len([l for l in snap.st_lines if l.is_valid]),
        }

    def export_all_st_lines(self, snapshots: Dict[str, TFAnalysisSnapshot]):
        all_lines = []
        for tf, snap in snapshots.items():
            for line in snap.st_lines:
                all_lines.append({
                    "timeframe": tf, "id": line.id, "price": line.price,
                    "direction": line.direction, "status": line.status,
                    "point_count": line.point_count, "start_ts": line.start_ts,
                    "end_ts": line.end_ts, "is_active": line.is_active, "is_valid": line.is_valid,
                })
        tf_order = {"4h": 0, "1h": 1, "30m": 2, "15m": 3, "5m": 4, "3m": 5, "1m": 6}
        all_lines.sort(key=lambda x: (tf_order.get(x["timeframe"], 99), x["price"]))
        data = {
            "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "total_lines": len(all_lines),
            "active_lines": sum(1 for l in all_lines if l["is_active"]),
            "valid_lines": sum(1 for l in all_lines if l["is_valid"]),
            "lines_by_tf": {}, "lines": all_lines,
        }
        for tf in ["4h", "1h", "30m", "15m", "5m", "3m", "1m"]:
            tf_lines = [l for l in all_lines if l["timeframe"] == tf]
            data["lines_by_tf"][tf] = {
                "total": len(tf_lines),
                "active": sum(1 for l in tf_lines if l["is_active"]),
                "bullish": sum(1 for l in tf_lines if l["direction"] == "BULLISH" and l["is_active"]),
                "bearish": sum(1 for l in tf_lines if l["direction"] == "BEARISH" and l["is_active"]),
            }
        with open(self.lines_dir / "all_st_lines.json", "w") as f:
            json.dump(data, f, indent=2, default=str)

    def export_global_state(self, state: MultiTFState, confluence=None, decision=None):
        data = {
            "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "total_candles_processed": state.total_candles_processed,
            "timeframes_ready": list(state.snapshots.keys()),
            "tf_summary": {},
            "confluence": confluence.to_dict() if confluence else None,
            "last_decision": decision.to_dict() if decision else None,
        }
        for tf, snap in state.snapshots.items():
            data["tf_summary"][tf] = {
                "price": snap.price, "trend": snap.trend_state,
                "form": snap.structural_form, "macd": snap.macd_bucket,
                "oi": snap.oi_state, "priority": snap.stack_priority,
                "compressed": snap.compressed, "wave_dir": snap.wave_direction,
                "active_lines": len([l for l in snap.st_lines if l.is_active]),
                "support": snap.nearest_support, "resistance": snap.nearest_resistance,
            }
        with open(self.global_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
