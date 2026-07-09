"""Test MultiTFDecisionMaker — guard_line_id resolution, gates, entry levels."""
from multi_tf_bot.multi_tf_decision import MultiTFDecisionMaker
from multi_tf_bot.models import (
    ConfluenceResult, ConfluenceZone, TFAnalysisSnapshot, STLineRecord,
)


def make_confluence(direction="BULLISH", score=0.8, aligned=4, conflict=False):
    zone = ConfluenceZone(
        price_center=50000.0, price_low=49900.0, price_high=50100.0,
        direction=direction, tf_count=3, timeframes=["4h", "1h", "15m"],
        line_ids=["L1", "L2", "L3"], strength=0.85,
    )
    return ConfluenceResult(
        timestamp=1000, price=50000.0, confluence_score=score,
        dominant_direction=direction,
        tf_alignment={"4h": direction, "1h": direction, "15m": direction, "5m": direction},
        zones=[zone], conflict_detected=conflict,
        reasoning="TEST", tf_count_aligned=aligned, total_tf_evaluated=7,
    )


def make_snap(tf: str, trend="UPTREND", support=49500.0, resistance=50500.0,
              lines=None) -> TFAnalysisSnapshot:
    if lines is None:
        line = STLineRecord(
            id=f"ST_{tf}_001", price=support, direction="BULLISH",
            status="VALID", point_count=10, start_ts=0, end_ts=None, timeframe=tf,
        )
        lines = [line]
    return TFAnalysisSnapshot(
        timeframe=tf, timestamp=1000, price=50000.0,
        trend_state=trend, macd_bucket="BULLISH", oi_state="INCREASING",
        st_lines=lines, nearest_support=support, nearest_resistance=resistance,
    )


class TestCalculateLevels:
    """_calculate_levels harus return 6 values termasuk guard_line_id dan guard_line_tf."""

    def setup_method(self):
        self.maker = MultiTFDecisionMaker({
            "tf_weights": {"4h": 0.3, "1h": 0.25, "15m": 0.15},
            "confluence_thresholds": {"strong": 0.75, "moderate": 0.55, "weak": 0.35},
            "min_tf_aligned": 3,
            "mode": "LONG_ONLY",
        })

    def test_return_six_values(self):
        """_calculate_levels harus return tuple of 6."""
        confluence = make_confluence()
        snapshots = {"4h": make_snap("4h")}

        result = self.maker._calculate_levels(confluence, 50000.0, "BULLISH", snapshots)
        assert len(result) == 6, f"Expected 6 values, got {len(result)}"
        entry_low, entry_high, sl, tp, guard_id, guard_tf = result
        assert entry_low is not None
        assert entry_high is not None
        assert sl is not None
        assert tp is not None

    def test_guard_line_id_from_4h(self):
        """Guard line ID diambil dari TF 4h."""
        confluence = make_confluence()
        snapshots = {"4h": make_snap("4h")}
        result = self.maker._calculate_levels(confluence, 50000.0, "BULLISH", snapshots)
        _, _, _, _, guard_id, guard_tf = result
        assert guard_id == "ST_4h_001", f"Expected ST_4h_001, got {guard_id}"
        assert guard_tf == "4h"

    def test_guard_line_id_fallback_to_1h(self):
        """Jika 4h tidak punya support, coba 1h."""
        confluence = make_confluence()
        snap_4h = make_snap("4h", support=None, resistance=None, lines=[])
        snap_1h = make_snap("1h", support=49600.0)
        snapshots = {"4h": snap_4h, "1h": snap_1h}
        result = self.maker._calculate_levels(confluence, 50000.0, "BULLISH", snapshots)
        _, _, _, _, guard_id, guard_tf = result
        # Line ST_1h_001 price=49600, support=49600, tolerance 0.05%
        assert guard_id == "ST_1h_001"
        assert guard_tf == "1h"

    def test_guard_line_id_none_when_no_match(self):
        """Jika tidak ada ST line yang cocok dengan support/resistance, guard_id = None."""
        confluence = make_confluence()
        empty_snap = TFAnalysisSnapshot(
            timeframe="4h", timestamp=1000, price=50000.0, st_lines=[],
        )
        snapshots = {"4h": empty_snap}
        result = self.maker._calculate_levels(confluence, 50000.0, "BULLISH", snapshots)
        _, _, _, _, guard_id, guard_tf = result
        assert guard_id is None
        assert guard_tf is None


class TestEvaluateGates:
    def setup_method(self):
        self.maker = MultiTFDecisionMaker({
            "tf_weights": {"4h": 0.3, "1h": 0.25, "15m": 0.15},
            "confluence_thresholds": {"strong": 0.75, "moderate": 0.55, "weak": 0.35},
            "min_tf_aligned": 3,
            "mode": "LONG_ONLY",
        })

    def test_reject_insufficient_alignment(self):
        """Gate 1: min_tf_aligned."""
        c = make_confluence(aligned=2)
        d = self.maker.evaluate(c, 50000.0)
        assert d.should_trade is False
        assert "INSUFFICIENT_ALIGNMENT" in d.rejection_reason

    def test_reject_conflict(self):
        """Gate 2: conflict_detected."""
        c = make_confluence(conflict=True)
        d = self.maker.evaluate(c, 50000.0)
        assert d.should_trade is False
        assert d.rejection_reason == "CONFLICT_DETECTED"

    def test_reject_neutral(self):
        """Gate 3: NEUTRAL direction."""
        c = make_confluence(direction="NEUTRAL", score=0.0)
        d = self.maker.evaluate(c, 50000.0)
        assert d.should_trade is False
        assert d.rejection_reason == "NEUTRAL_DIRECTION"

    def test_reject_mode_filter_short(self):
        """Gate 4: LONG_ONLY mode rejects BEARISH."""
        c = make_confluence(direction="BEARISH")
        d = self.maker.evaluate(c, 50000.0)
        assert d.should_trade is False
        assert "MODE_FILTER" in d.rejection_reason

    def test_reject_low_confluence(self):
        """Gate 5: score below weak_threshold."""
        c = make_confluence(score=0.2)
        d = self.maker.evaluate(c, 50000.0)
        assert d.should_trade is False
        assert "LOW_CONFLUENCE" in d.rejection_reason

    def test_approve_bullish(self):
        """All gates pass -> should_trade=True."""
        snapshots = {"4h": make_snap("4h")}
        c = make_confluence()
        d = self.maker.evaluate(c, 50000.0, snapshots=snapshots)
        assert d.should_trade is True
        assert d.direction == "BULLISH"
        assert d.guard_line_id is not None
        assert d.guard_line_tf is not None

    def test_confidence_includes_river(self):
        """final_confidence = score*0.7 + river_confidence*0.3."""
        snapshots = {"4h": make_snap("4h")}
        c = make_confluence(score=0.8)
        d = self.maker.evaluate(c, 50000.0, river_confidence=0.5, river_should_enter=True, snapshots=snapshots)
        expected = round(0.8 * 0.7 + 0.5 * 0.3, 4)
        assert d.confidence == expected
