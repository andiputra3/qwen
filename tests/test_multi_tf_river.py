"""Test MultiTFRiver — pattern learning, should_enter, make_signature."""
import tempfile
import os
from multi_tf_bot.multi_tf_river import MultiTFRiver


class TestMakeSignature:
    def test_deterministic_order(self):
        alignment = {"5m": "BULLISH", "4h": "BULLISH", "1h": "BEARISH"}
        sig = MultiTFRiver.make_signature(alignment)
        parts = sig.split("|")
        assert parts[0].startswith("4h:")
        assert parts[1].startswith("1h:")
        assert parts[2].startswith("5m:")

    def test_skips_missing_tfs(self):
        alignment = {"4h": "BULLISH"}
        sig = MultiTFRiver.make_signature(alignment)
        assert sig == "4h:BULLISH"

    def test_empty_alignment(self):
        sig = MultiTFRiver.make_signature({})
        assert sig == ""


class TestRiverLearning:
    def setup_method(self):
        self.tmpfile = tempfile.mktemp(suffix=".json")
        self.river = MultiTFRiver(save_path=self.tmpfile)

    def teardown_method(self):
        if os.path.exists(self.tmpfile):
            os.unlink(self.tmpfile)

    def test_record_outcome_creates_pattern(self):
        alignment = {"4h": "BULLISH", "1h": "BULLISH"}
        self.river.record_outcome(alignment, 0.8, 2.5, 1000)
        sig = self.river.make_signature(alignment)
        assert sig in self.river._patterns
        p = self.river._patterns[sig]
        assert p.total_trades == 1
        assert p.total_pnl == 2.5
        assert p.avg_confluence_score == 0.8

    def test_record_multiple_outcomes(self):
        alignment = {"4h": "BULLISH"}
        self.river.record_outcome(alignment, 0.8, 2.0, 1000)
        self.river.record_outcome(alignment, 0.7, -1.0, 2000)
        sig = self.river.make_signature(alignment)
        p = self.river._patterns[sig]
        assert p.total_trades == 2
        assert p.total_pnl == 1.0
        assert p.wins == 1
        assert p.losses == 1

    def test_should_enter_false_new_pattern(self):
        alignment = {"4h": "BULLISH"}
        should, conf = self.river.should_enter(alignment, 0.8)
        assert should is False
        assert conf == 0.0

    def test_should_enter_after_enough_samples(self):
        alignment = {"4h": "BULLISH"}
        for i in range(6):
            self.river.record_outcome(alignment, 0.8, 2.0 if i < 4 else -1.0, i * 1000)
        should, conf = self.river.should_enter(alignment, 0.8)
        p = self.river._patterns[self.river.make_signature(alignment)]
        assert p.total_trades == 6
        assert conf > 0

    def test_persistence(self):
        alignment = {"4h": "BULLISH"}
        self.river.record_outcome(alignment, 0.8, 2.5, 1000)

        river2 = MultiTFRiver(save_path=self.tmpfile)
        sig = river2.make_signature(alignment)
        assert sig in river2._patterns
        assert river2._patterns[sig].total_pnl == 2.5

    def test_get_top_patterns(self):
        for i in range(6):
            self.river.record_outcome({"4h": "BULLISH"}, 0.8, 2.0, i * 1000)
        tops = self.river.get_top_patterns(5)
        assert len(tops) >= 1
        assert tops[0].total_trades >= 5
