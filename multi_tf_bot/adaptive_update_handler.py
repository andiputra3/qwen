"""
Adaptive Update Handler - Phase 3
Monitors ST line changes across all timeframes.
Triggers re-evaluation when structural changes are significant.
Can force-exit trades if confluence deteriorates.
"""
import logging
import time
from typing import Dict, List
from multi_tf_bot.models import TFAnalysisSnapshot, ConfluenceResult

logger = logging.getLogger(__name__)


class AdaptiveUpdateHandler:
    """
    Detects significant structural changes and triggers actions:
    1. Re-evaluate confluence when ST lines flip
    2. Force-exit trades if confluence drops below threshold
    3. Log structural evolution for analysis
    """

    def __init__(self, config: dict):
        self.min_confluence_for_hold = config.get("min_confluence_for_hold", 0.4)
        self.max_conflict_tolerance = config.get("max_conflict_tolerance", 0.3)
        self._previous_line_counts: Dict[str, int] = {}
        self._previous_trends: Dict[str, str] = {}
        self._structural_changes: List[dict] = []

    def check_structural_changes(
        self, snapshots: Dict[str, TFAnalysisSnapshot]
    ) -> List[str]:
        """
        Detect structural changes across all TFs.
        Returns list of changed TFs.
        """
        changed_tfs = []

        for tf, snap in snapshots.items():
            current_count = len([l for l in snap.st_lines if l.is_active])
            prev_count = self._previous_line_counts.get(tf, 0)

            current_trend = snap.trend_state
            prev_trend = self._previous_trends.get(tf, "UNKNOWN")

            if current_count != prev_count or current_trend != prev_trend:
                changed_tfs.append(tf)
                self._log_change(tf, prev_count, current_count, prev_trend, current_trend)

            self._previous_line_counts[tf] = current_count
            self._previous_trends[tf] = current_trend

        return changed_tfs

    def should_force_exit(
        self, current_confluence: ConfluenceResult, has_open_position: bool
    ) -> tuple:
        """Determine if open position should be force-exited."""
        if not has_open_position:
            return False, None

        if current_confluence.confluence_score < self.min_confluence_for_hold:
            return True, f"CONFLUENCE_DROPPED ({current_confluence.confluence_score:.3f}<{self.min_confluence_for_hold})"

        if current_confluence.conflict_detected:
            return True, f"CONFLICT_DETECTED (score={current_confluence.confluence_score:.3f})"

        return False, None

    def should_force_exit_for_direction(
        self, current_confluence: ConfluenceResult, position_direction: str
    ) -> tuple:
        """Check if confluence flipped against current position direction."""
        if current_confluence.dominant_direction == "NEUTRAL":
            return False, None

        if current_confluence.dominant_direction != position_direction:
            return True, f"DIRECTION_FLIPPED ({position_direction}->{current_confluence.dominant_direction})"

        return False, None

    def _log_change(
        self, tf: str, prev_count: int, current_count: int,
        prev_trend: str, current_trend: str
    ):
        """Log structural change for analysis."""
        change = {
            "tf": tf,
            "prev_lines": prev_count,
            "current_lines": current_count,
            "prev_trend": prev_trend,
            "current_trend": current_trend,
            "timestamp": time.time(),
        }
        self._structural_changes.append(change)

        logger.info(
            f"[ADAPTIVE] {tf} structural change: "
            f"Lines {prev_count}->{current_count} | Trend {prev_trend}->{current_trend}"
        )

    def get_change_history(self, limit: int = 50) -> List[dict]:
        return self._structural_changes[-limit:]

    def reset(self):
        self._previous_line_counts.clear()
        self._previous_trends.clear()
        self._structural_changes.clear()
