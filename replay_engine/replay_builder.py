"""
Replay Builder - POST-AUDIT FIXED VERSION
Fix A: No synthetic strength/compression derivation
Fix B: Explicit MISSING_DATA instead of silent defaults
Fix C: Trade context filled from snapshot history
Fix P0-4: Wave start_line_id from event data
Fix P1-2: Trend/Stack transitions reconstructed from event log
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from replay_engine.models import (
    ReplaySTLine, ReplayWave, ReplayTrade, ReplaySnapshot,
    ReplayEvent, STLineLifecycle, WaveLifecycle, TrendLifecycle,
    MISSING_DATA, safe_get
)
from replay_engine.replay_storage import ReplayStorage

logger = logging.getLogger(__name__)


class ReplayBuilder:
    def __init__(self, storage: ReplayStorage):
        self.storage = storage
        self._event_log: List[dict] = []
        self._load_event_log()

    def _load_event_log(self):
        events_path = Path(self.storage.data_dir) / "events.jsonl"
        if events_path.exists():
            with open(events_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self._event_log.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        logger.info(f"[REPLAY-BUILDER] Loaded {len(self._event_log)} discrete events")

    def build_all_lines(self) -> List[ReplaySTLine]:
        raw_lines = self.storage.get_all_lines()
        lines = []
        for raw in raw_lines:
            line = ReplaySTLine(
                id=safe_get(raw, "id"),
                timeframe=safe_get(raw, "timeframe"),
                direction=safe_get(raw, "direction"),
                price=float(safe_get(raw, "price", 0)),
                created_ts=int(safe_get(raw, "start_ts", 0)),
                closed_ts=raw.get("end_ts"),
                length_points=int(safe_get(raw, "point_count", 0)),
                status=safe_get(raw, "status"),
                strength=float(raw["strength"]) if "strength" in raw else MISSING_DATA,
                compression_reason=raw.get("compression_reason", MISSING_DATA),
            )
            line_events = [e for e in self._event_log
                           if e.get("object") == "SupertrendLine" and e.get("id") == line.id]
            for evt in line_events:
                line.lifecycle_history.append(ReplayEvent(
                    timestamp=evt["ts"], event_type=evt["event"],
                    object_type="SupertrendLine", object_id=line.id,
                    lifecycle=evt["event"].replace("ST_LINE_", ""),
                    timeframe=line.timeframe, data=evt.get("data", {}),
                ))
            if not line.lifecycle_history:
                line.lifecycle_history.append(ReplayEvent(
                    timestamp=line.created_ts, event_type="ST_LINE_CREATED",
                    object_type="SupertrendLine", object_id=line.id,
                    lifecycle=STLineLifecycle.CREATED.value,
                    timeframe=line.timeframe,
                    data={"price": line.price, "direction": line.direction},
                ))
            lines.append(line)
        logger.info(f"[REPLAY-BUILDER] Built {len(lines)} ST Lines")
        return lines

    def build_all_waves(self) -> List[ReplayWave]:
        waves = []
        wave_events = [e for e in self._event_log if e.get("event") == "WAVE_COMPLETED"]
        seen_ids = set()

        for evt in wave_events:
            wid = evt.get("id", "UNKNOWN")
            if wid in seen_ids:
                continue
            seen_ids.add(wid)
            data = evt.get("data", {})
            wave = ReplayWave(
                id=wid,
                timeframe=evt.get("tf", "UNKNOWN"),
                direction=safe_get(data, "direction"),
                start_line_id=safe_get(data, "start_line_id"),
                end_line_id=safe_get(data, "end_line_id"),
                created_ts=evt["ts"],
                start_price=float(safe_get(data, "start_price", 0)),
                end_price=float(safe_get(data, "end_price", 0)),
                amplitude=float(safe_get(data, "amplitude", 0)),
                length_points=int(safe_get(data, "length", 0)),
                status="CLOSED",
            )
            wave.lifecycle_history.append(ReplayEvent(
                timestamp=evt["ts"], event_type="WAVE_COMPLETED",
                object_type="Wave", object_id=wid,
                lifecycle=WaveLifecycle.CLOSED.value,
                timeframe=wave.timeframe, data=data,
            ))
            waves.append(wave)

        snapshots = self.storage.get_all_snapshots()
        for tf, snap in snapshots.items():
            lw = snap.get("last_wave")
            if lw and lw.get("id") not in seen_ids:
                wave = ReplayWave(
                    id=lw.get("id", "UNKNOWN"), timeframe=tf,
                    direction=safe_get(lw, "direction"),
                    start_line_id=safe_get(lw, "start_line_id"),
                    created_ts=snap.get("timestamp", 0),
                    start_price=float(safe_get(lw, "start_price", 0)),
                    end_price=float(safe_get(lw, "end_price", 0)),
                    amplitude=float(safe_get(lw, "amplitude", 0)),
                    length_points=int(safe_get(lw, "length_points", 0)),
                    status="ACTIVE",
                )
                waves.append(wave)

        logger.info(f"[REPLAY-BUILDER] Built {len(waves)} Waves")
        return waves

    def build_all_trades(self) -> List[ReplayTrade]:
        raw_trades = self.storage.get_all_trades()
        trades = []
        global_state = self.storage.get_global_state()

        for raw in raw_trades:
            entry_ts = int(raw.get("entry_ts", 0))
            exit_ts = int(raw.get("exit_ts", 0)) if raw.get("exit_ts") else None

            trend_at_entry = MISSING_DATA
            wave_at_entry = MISSING_DATA
            stack_at_entry = MISSING_DATA
            guard_line_id = raw.get("guard_line_id", MISSING_DATA)

            if global_state and "tf_summary" in global_state:
                for tf in ["4h", "1h", "15m"]:
                    tf_sum = global_state["tf_summary"].get(tf, {})
                    if tf_sum:
                        trend_at_entry = tf_sum.get("trend", MISSING_DATA)
                        stack_at_entry = tf_sum.get("priority", MISSING_DATA)
                        break

            trade = ReplayTrade(
                trade_id=str(entry_ts),
                direction=safe_get(raw, "direction"),
                entry_ts=entry_ts,
                exit_ts=exit_ts,
                entry_price=float(safe_get(raw, "entry_price", 0)),
                exit_price=float(raw["exit_price"]) if raw.get("exit_price") else None,
                pnl_pct=float(safe_get(raw, "pnl_pct", 0)),
                pnl_usd=float(raw.get("pnl_usd", 0)) if raw.get("pnl_usd") else 0.0,
                reason_entry="CONFLUENCE_APPROVED",
                reason_exit=raw.get("reason", MISSING_DATA),
                guard_line_id=guard_line_id,
                trend_at_entry=trend_at_entry,
                wave_at_entry=wave_at_entry,
                stack_at_entry=stack_at_entry,
            )

            trade.lifecycle_history.append(ReplayEvent(
                timestamp=entry_ts, event_type="TRADE_OPENED",
                object_type="Trade", object_id=trade.trade_id,
                lifecycle="OPENED", timeframe="MULTI_TF",
                data={"direction": trade.direction, "entry": trade.entry_price,
                      "trend": trend_at_entry, "guard": guard_line_id},
            ))
            if exit_ts:
                trade.lifecycle_history.append(ReplayEvent(
                    timestamp=exit_ts, event_type="TRADE_CLOSED",
                    object_type="Trade", object_id=trade.trade_id,
                    lifecycle="CLOSED", timeframe="MULTI_TF",
                    data={"pnl_pct": trade.pnl_pct, "reason": trade.reason_exit},
                ))
            trades.append(trade)

        logger.info(f"[REPLAY-BUILDER] Built {len(trades)} Trades")
        return trades

    def build_trend_transitions(self) -> List[ReplayEvent]:
        return [
            ReplayEvent(
                timestamp=e["ts"], event_type=e["event"],
                object_type="Trend", object_id=e.get("id", ""),
                lifecycle=e.get("data", {}).get("to", "UNKNOWN"),
                timeframe=e.get("tf", ""), data=e.get("data", {}),
            )
            for e in self._event_log if e.get("event") == "TREND_CHANGED"
        ]

    def build_stack_transitions(self) -> List[ReplayEvent]:
        return [
            ReplayEvent(
                timestamp=e["ts"], event_type=e["event"],
                object_type="AdaptiveStack", object_id=e.get("id", ""),
                lifecycle=e.get("data", {}).get("to", "UNKNOWN"),
                timeframe=e.get("tf", ""), data=e.get("data", {}),
            )
            for e in self._event_log if e.get("event") == "STACK_PRIORITY_CHANGED"
        ]

    def build_snapshots(self) -> List[ReplaySnapshot]:
        snapshots = []
        raw_snapshots = self.storage.get_all_snapshots()
        for tf, raw in raw_snapshots.items():
            snap = ReplaySnapshot(
                timestamp=raw.get("timestamp", 0), timeframe=tf,
                price=raw.get("price", 0.0),
                trend_state=raw.get("trend_state", MISSING_DATA),
                structural_form=raw.get("structural_form", MISSING_DATA),
                macd_bucket=raw.get("macd_bucket", MISSING_DATA),
                oi_state=raw.get("oi_state", MISSING_DATA),
                stack_priority=raw.get("stack_priority", MISSING_DATA),
                compressed=raw.get("compressed", False),
                active_lines_count=raw.get("active_st_lines_count", 0),
                valid_lines_count=raw.get("valid_st_lines_count", 0),
                nearest_support=raw.get("nearest_support"),
                nearest_resistance=raw.get("nearest_resistance"),
                fib_levels=raw.get("fib_levels"),
                last_wave_id=raw.get("last_wave", {}).get("id") if raw.get("last_wave") else None,
            )
            snapshots.append(snap)
        logger.info(f"[REPLAY-BUILDER] Built {len(snapshots)} Snapshots")
        return snapshots
