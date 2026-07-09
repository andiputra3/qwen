"""Test ConfluenceEngine._tf_direction — MACD+OI override for SIDEWAY trend."""
from multi_tf_bot.confluence_engine import ConfluenceEngine
from multi_tf_bot.models import TFAnalysisSnapshot


def make_snap(trend_state="SIDEWAY", macd="NEUTRAL", oi="ABSENT",
              wave_direction=None) -> TFAnalysisSnapshot:
    return TFAnalysisSnapshot(
        timeframe="4h", timestamp=1000, price=50000.0,
        trend_state=trend_state, macd_bucket=macd, oi_state=oi,
        wave_direction=wave_direction,
    )


class TestTfDirection:
    """Verifikasi _tf_direction: UPTREND/DOWNTREND = authority.
    SIDEWAY + MACD BULLISH + OI INCREASING = BULLISH.
    SIDEWAY + MACD BEARISH + OI INCREASING = BEARISH.
    SIDEWAY alone = NEUTRAL (MACD/OI can override).
    wave_direction dengan MACD WEAKENING."""

    def setup_method(self):
        self.engine = ConfluenceEngine(config={
            "tf_weights": {"4h": 0.3, "1h": 0.25},
            "confluence_thresholds": {"strong": 0.75, "moderate": 0.55},
        })

    def test_uptrend_bullish(self):
        snap = make_snap(trend_state="UPTREND")
        result = self.engine._tf_direction(snap)
        assert result == "BULLISH", f"UPTREND should be BULLISH, got {result}"

    def test_downtrend_bearish(self):
        snap = make_snap(trend_state="DOWNTREND")
        result = self.engine._tf_direction(snap)
        assert result == "BEARISH", f"DOWNTREND should be BEARISH, got {result}"

    def test_sideway_macd_bullish_oi_increasing(self):
        """Fix B3: SIDEWAY + MACD BULLISH + OI INCREASING -> NEUTRAL (no override)"""
        snap = make_snap(trend_state="SIDEWAY", macd="BULLISH", oi="INCREASING")
        result = self.engine._tf_direction(snap)
        assert result == "NEUTRAL", (
            f"SIDEWAY+MACD BULLISH+OI INCREASING should be NEUTRAL (no override), got {result}"
        )

    def test_sideway_macd_bearish_oi_increasing(self):
        """Fix B3: SIDEWAY + MACD BEARISH + OI INCREASING -> NEUTRAL (no override)"""
        snap = make_snap(trend_state="SIDEWAY", macd="BEARISH", oi="INCREASING")
        result = self.engine._tf_direction(snap)
        assert result == "NEUTRAL", (
            f"SIDEWAY+MACD BEARISH+OI INCREASING should be NEUTRAL (no override), got {result}"
        )

    def test_sideway_macd_bullish_oi_decreasing(self):
        """SIDEWAY + MACD BULLISH + OI DECREASING -> fall through to wave check"""
        snap = make_snap(trend_state="SIDEWAY", macd="BULLISH", oi="DECREASING")
        result = self.engine._tf_direction(snap)
        assert result == "NEUTRAL"

    def test_sideway_macd_bearish_oi_decreasing(self):
        snap = make_snap(trend_state="SIDEWAY", macd="BEARISH", oi="DECREASING")
        result = self.engine._tf_direction(snap)
        assert result == "NEUTRAL"

    def test_sideway_macd_neutral_oi_absent(self):
        """SIDEWAY alone with no MACD/OI -> wave check, then NEUTRAL."""
        snap = make_snap(trend_state="SIDEWAY")
        result = self.engine._tf_direction(snap)
        assert result == "NEUTRAL"

    def test_wave_bullish_macd_bullish(self):
        snap = make_snap(trend_state="SIDEWAY", macd="BULLISH", wave_direction="BULLISH")
        result = self.engine._tf_direction(snap)
        assert result == "BULLISH"

    def test_wave_bullish_macd_weakening(self):
        snap = make_snap(trend_state="SIDEWAY", macd="WEAKENING", wave_direction="BULLISH")
        result = self.engine._tf_direction(snap)
        assert result == "BULLISH"

    def test_wave_bearish_macd_weakening(self):
        snap = make_snap(trend_state="SIDEWAY", macd="WEAKENING", wave_direction="BEARISH")
        result = self.engine._tf_direction(snap)
        assert result == "BEARISH"

    def test_wave_bullish_macd_bearish(self):
        """Wave BULLISH but MACD BEARISH (not WEAKENING) -> wave not enough."""
        snap = make_snap(trend_state="SIDEWAY", macd="BEARISH", wave_direction="BULLISH")
        result = self.engine._tf_direction(snap)
        assert result == "NEUTRAL"


class TestConfluenceScore:
    def setup_method(self):
        self.engine = ConfluenceEngine(config={
            "tf_weights": {"4h": 0.3, "1h": 0.25, "15m": 0.15},
            "confluence_thresholds": {"strong": 0.75, "moderate": 0.55},
        })

    def test_all_bullish(self):
        alignment = {"4h": "BULLISH", "1h": "BULLISH", "15m": "BULLISH"}
        score, direction, conflict = self.engine._score_alignment(alignment)
        assert direction == "BULLISH"
        assert score >= 0.8
        assert conflict is False

    def test_all_bearish(self):
        alignment = {"4h": "BEARISH", "1h": "BEARISH", "15m": "BEARISH"}
        score, direction, conflict = self.engine._score_alignment(alignment)
        assert direction == "BEARISH"
        assert score >= 0.8
        assert conflict is False

    def test_conflict_detected(self):
        alignment = {"4h": "BULLISH", "1h": "BEARISH", "15m": "BULLISH"}
        score, direction, conflict = self.engine._score_alignment(alignment)
        assert conflict is True
        assert direction == "BULLISH"

    def test_all_neutral(self):
        alignment = {"4h": "NEUTRAL", "1h": "NEUTRAL"}
        score, direction, conflict = self.engine._score_alignment(alignment)
        assert direction == "NEUTRAL"
        assert score == 0.0

    def test_mixed_dominance(self):
        alignment = {"4h": "BULLISH", "1h": "NEUTRAL", "15m": "NEUTRAL"}
        score, direction, conflict = self.engine._score_alignment(alignment)
        assert direction == "BULLISH"
        assert conflict is False
