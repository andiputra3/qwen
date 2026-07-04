from decimal import Decimal
from multi_tf_bot.models import (
    TradeDecision, ConfluenceResult, ConfluenceZone,
    STLineRecord, WaveRecord, TFAnalysisSnapshot, MultiTFState,
)


class TestTradeDecision:
    def test_has_guard_line_fields(self):
        d = TradeDecision(timestamp=0, should_trade=True, direction="BULLISH", confidence=0.8)
        assert hasattr(d, "guard_line_id")
        assert hasattr(d, "guard_line_tf")
        assert d.guard_line_id is None
        assert d.guard_line_tf is None

    def test_guard_line_fields_set(self):
        d = TradeDecision(
            timestamp=0, should_trade=True, direction="BULLISH", confidence=0.8,
            guard_line_id="ST_LINE_001", guard_line_tf="4h",
        )
        assert d.guard_line_id == "ST_LINE_001"
        assert d.guard_line_tf == "4h"

    def test_to_dict_includes_guard_fields(self):
        d = TradeDecision(
            timestamp=1000, should_trade=True, direction="BULLISH", confidence=0.8,
            guard_line_id="ST_LINE_001", guard_line_tf="4h",
        )
        result = d.to_dict()
        assert result["guard_id"] == "ST_LINE_001"
        assert result["guard_tf"] == "4h"

    def test_to_dict_guard_fields_none(self):
        d = TradeDecision(timestamp=0, should_trade=False, direction="NEUTRAL", confidence=0.0)
        result = d.to_dict()
        assert result["guard_id"] is None
        assert result["guard_tf"] is None

    def test_rejection_decision_no_guard(self):
        d = TradeDecision(
            timestamp=0, should_trade=False, direction="NEUTRAL", confidence=0.0,
            rejection_reason="TEST",
        )
        assert d.guard_line_id is None
        assert d.guard_line_tf is None

    def test_default_values(self):
        d = TradeDecision(timestamp=0, should_trade=True, direction="BULLISH", confidence=0.8)
        assert d.entry_zone_low is None
        assert d.entry_zone_high is None
        assert d.stop_loss is None
        assert d.take_profit is None
        assert d.position_size_pct == 0.0
        assert d.confluence is None
        assert d.river_confidence == 0.0
        assert d.river_should_enter is False
        assert d.reasoning == ""
        assert d.rejection_reason is None


class TestSTLineRecord:
    def test_is_active(self):
        r = STLineRecord(id="L1", price=100.0, direction="BULLISH", status="VALID",
                         point_count=5, start_ts=0, end_ts=None, timeframe="4h")
        assert r.is_active is True
        assert r.is_valid is True

    def test_is_active_pending(self):
        r = STLineRecord(id="L2", price=101.0, direction="BULLISH", status="PENDING",
                         point_count=2, start_ts=0, end_ts=None, timeframe="4h")
        assert r.is_active is True
        assert r.is_valid is False

    def test_is_not_active(self):
        r = STLineRecord(id="L3", price=102.0, direction="BEARISH", status="DEACTIVATED",
                         point_count=10, start_ts=0, end_ts=100, timeframe="1h")
        assert r.is_active is False
        assert r.is_valid is False


class TestConfluenceResult:
    def test_to_dict(self):
        zone = ConfluenceZone(
            price_center=50000.0, price_low=49900.0, price_high=50100.0,
            direction="BULLISH", tf_count=3, timeframes=["4h", "1h", "15m"],
            line_ids=["L1", "L2", "L3"], strength=0.85,
        )
        result = ConfluenceResult(
            timestamp=1000, price=50000.0, confluence_score=0.85,
            dominant_direction="BULLISH", tf_alignment={"4h": "BULLISH", "1h": "BULLISH"},
            zones=[zone], conflict_detected=False,
            reasoning="TEST", tf_count_aligned=2, total_tf_evaluated=2,
        )
        d = result.to_dict()
        assert d["score"] == 0.85
        assert d["direction"] == "BULLISH"
        assert d["aligned"] == 2
        assert d["total"] == 2
        assert d["zones"] == 1
        assert d["conflict"] is False


class TestTFAnalysisSnapshot:
    def test_to_dict(self):
        snap = TFAnalysisSnapshot(
            timeframe="4h", timestamp=1000, price=50000.0,
            trend_state="UPTREND", macd_bucket="BULLISH", oi_state="INCREASING",
            wave_direction="BULLISH", wave_length=10,
            nearest_support=49500.0, nearest_resistance=50500.0,
        )
        d = snap.to_dict()
        assert d["tf"] == "4h"
        assert d["trend"] == "UPTREND"
        assert d["macd"] == "BULLISH"
        assert d["oi"] == "INCREASING"
        assert d["support"] == 49500.0
        assert d["resistance"] == 50500.0
        assert d["wave_dir"] == "BULLISH"

    def test_to_dict_no_lines(self):
        snap = TFAnalysisSnapshot(timeframe="1m", timestamp=0, price=0.0)
        d = snap.to_dict()
        assert d["active_lines"] == 0
        assert d["valid_lines"] == 0


class TestMultiTFState:
    def test_empty_state(self):
        state = MultiTFState()
        assert state.snapshots == {}
        assert state.total_candles_processed == 0
        assert state.last_confluence_ts == 0
        assert state.last_decision is None

    def test_all_tfs_ready(self):
        state = MultiTFState()
        snap = TFAnalysisSnapshot(timeframe="4h", timestamp=0, price=0.0)
        state.snapshots["4h"] = snap
        assert state.all_tfs_ready(["4h"]) is True
        assert state.all_tfs_ready(["4h", "1h"]) is False

    def test_summary(self):
        state = MultiTFState()
        snap = TFAnalysisSnapshot(timeframe="4h", timestamp=1000, price=50000.0, trend_state="UPTREND")
        state.snapshots["4h"] = snap
        state.total_candles_processed = 100
        s = state.summary()
        assert "4h" in s["timeframes"]
        assert s["total_candles"] == 100
        assert s["trends"]["4h"] == "UPTREND"
