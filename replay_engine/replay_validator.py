"""
Replay Validator - POST-AUDIT FIXED VERSION
Fix P1-9: Weighted consistency scoring
"""
import logging
from typing import List, Dict
from replay_engine.models import ReplayAuditResult, ReplaySTLine, ReplayWave, ReplayTrade
from replay_engine.replay_timeline import ReplayTimeline

logger = logging.getLogger(__name__)

WEIGHTS = {
    "broken_timelines": 10.0,
    "broken_links": 5.0,
    "orphan_objects": 3.0,
    "missing_snapshots": 2.0,
    "missing_events": 1.0,
}


class ReplayValidator:
    def validate(
        self,
        timeline: ReplayTimeline,
        lines: List[ReplaySTLine],
        waves: List[ReplayWave],
        trades: List[ReplayTrade],
    ) -> ReplayAuditResult:
        audit = ReplayAuditResult()
        audit.total_events = len(timeline.events)
        audit.total_lines = len(lines)
        audit.total_waves = len(waves)
        audit.total_trades = len(trades)

        timeline.sort()
        if timeline.events:
            for i in range(1, len(timeline.events)):
                if timeline.events[i].timestamp < timeline.events[i-1].timestamp:
                    audit.broken_timelines.append(
                        f"TIMELINE_BREAK at index {i}: "
                        f"{timeline.events[i-1].timestamp} > {timeline.events[i].timestamp}"
                    )

        line_ids_in_timeline = set(
            e.object_id for e in timeline.events if e.object_type == "SupertrendLine"
        )
        for line in lines:
            if line.id not in line_ids_in_timeline:
                audit.orphan_objects.append(f"ORPHAN_LINE: {line.id}")

        wave_ids_in_timeline = set(
            e.object_id for e in timeline.events if e.object_type == "Wave"
        )
        for wave in waves:
            if wave.id not in wave_ids_in_timeline:
                audit.orphan_objects.append(f"ORPHAN_WAVE: {wave.id}")

        for trade in trades:
            if not trade.guard_line_id:
                audit.broken_links.append(f"TRADE_MISSING_GUARD: {trade.trade_id}")
            if not trade.trend_at_entry:
                audit.broken_links.append(f"TRADE_MISSING_TREND: {trade.trade_id}")

        timeline_tfs = set(e.timeframe for e in timeline.events)
        expected_tfs = {"1m", "3m", "5m", "15m", "30m", "1h", "4h"}
        missing_tfs = expected_tfs - timeline_tfs
        for tf in missing_tfs:
            audit.missing_snapshots.append(f"MISSING_TF_SNAPSHOT: {tf}")

        total_checks = max(
            audit.total_events + audit.total_lines + audit.total_waves + audit.total_trades, 1
        )

        weighted_issues = (
            len(audit.broken_timelines) * WEIGHTS["broken_timelines"] +
            len(audit.broken_links) * WEIGHTS["broken_links"] +
            len(audit.orphan_objects) * WEIGHTS["orphan_objects"] +
            len(audit.missing_snapshots) * WEIGHTS["missing_snapshots"] +
            len(audit.missing_events) * WEIGHTS["missing_events"]
        )
        max_possible_weight = total_checks * WEIGHTS["broken_timelines"]
        audit.consistency_score = max(0.0, 1.0 - (weighted_issues / max(max_possible_weight, 1)))

        total_issues = (
            len(audit.broken_timelines) + len(audit.broken_links) +
            len(audit.orphan_objects) + len(audit.missing_snapshots) +
            len(audit.missing_events)
        )

        if total_issues == 0:
            audit.certification = "PASS"
        elif audit.consistency_score >= 0.95:
            audit.certification = "CONDITIONAL_PASS"
            audit.issues.append(f"{total_issues} minor issues found")
        else:
            audit.certification = "FAIL"
            audit.issues.append(f"{total_issues} issues, score={audit.consistency_score:.4f}")

        logger.info(
            f"[REPLAY-VALIDATOR] Certification={audit.certification} | "
            f"Score={audit.consistency_score:.4f} | Issues={total_issues}"
        )
        return audit
