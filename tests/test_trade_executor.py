"""Test TradeExecutor — guard_line_id digunakan sebagai support_line_id, fallback."""
from decimal import Decimal
from multi_tf_bot.trade_executor import TradeExecutor
from multi_tf_bot.models import TradeDecision, ConfluenceResult


def make_decision(guard_line_id=None, guard_line_tf=None, should_trade=True):
    c = ConfluenceResult(
        timestamp=1000, price=50000.0, confluence_score=0.8,
        dominant_direction="BULLISH",
        tf_alignment={"4h": "BULLISH"}, zones=[], conflict_detected=False,
        reasoning="TEST", tf_count_aligned=4, total_tf_evaluated=7,
    )
    return TradeDecision(
        timestamp=1000, should_trade=should_trade, direction="BULLISH",
        confidence=0.8, entry_zone_low=49900.0, entry_zone_high=50100.0,
        stop_loss=49600.0, take_profit=51000.0, position_size_pct=100.0,
        confluence=c, reasoning="TEST", guard_line_id=guard_line_id,
        guard_line_tf=guard_line_tf,
    )


class TestDecisionToProposal:
    def setup_method(self):
        self.executor = TradeExecutor(
            account_balance=Decimal("10000"), leverage=10,
        )

    def test_guard_line_id_used_as_support_line_id(self):
        """support_line_id harus dari decision.guard_line_id."""
        decision = make_decision(guard_line_id="ST_4h_001", guard_line_tf="4h")
        proposal = self.executor._decision_to_proposal(decision)
        assert proposal is not None
        assert proposal.support_line_id == "ST_4h_001"

    def test_fallback_when_guard_line_id_none(self):
        """Jika guard_line_id None, BLOCKED (no fallback)."""
        decision = make_decision(guard_line_id=None)
        proposal = self.executor._decision_to_proposal(decision)
        assert proposal is None

    def test_fallback_when_guard_line_id_empty(self):
        """Edge case: guard_line_id None juga BLOCKED."""
        decision = make_decision(guard_line_id=None)
        proposal = self.executor._decision_to_proposal(decision)
        assert proposal is None

    def test_missing_entry_zone_returns_none(self):
        decision = make_decision()
        decision.entry_zone_low = None
        decision.entry_zone_high = None
        proposal = self.executor._decision_to_proposal(decision)
        assert proposal is None

    def test_missing_stop_loss_returns_none(self):
        decision = make_decision()
        decision.stop_loss = None
        proposal = self.executor._decision_to_proposal(decision)
        assert proposal is None

    def test_skip_rejected_decision(self):
        decision = make_decision(should_trade=False)
        result = self.executor.execute_decision(decision)
        assert result is False

    def test_proposal_id_format(self):
        decision = make_decision(guard_line_id="ST_4h_001")
        proposal = self.executor._decision_to_proposal(decision)
        assert proposal.id.startswith("MTF_")


class TestExecutorStatus:
    def setup_method(self):
        self.executor = TradeExecutor(
            account_balance=Decimal("10000"), leverage=10,
        )

    def test_initial_status(self):
        status = self.executor.get_status()
        assert status["account_balance"] == 10000.0
        assert status["open_trade"] is False
        assert status["trade_count"] == 0
        assert status["trade_history_count"] == 0
        assert status["last_trade_pnl"] is None
