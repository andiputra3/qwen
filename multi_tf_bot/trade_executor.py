"""
Trade Executor - Phase 3
Converts TradeDecision into actual trades via VirtualExecutor (File #35).
Manages position lifecycle and reports outcomes to River.
"""
import logging
from decimal import Decimal
from typing import Optional, Callable
import uuid

from st_lms_core.execution.virtual_executor import VirtualExecutor
from st_lms_core.core.models.trade import TradeProposal, AuthorizationResult, ExitSignal
from st_lms_core.core.models.enums import Direction, ExitTrigger
from multi_tf_bot.models import TradeDecision

logger = logging.getLogger(__name__)


class TradeExecutor:
    """
    Executes TradeDecision from Multi-TF Decision Maker.
    Uses VirtualExecutor (File #35) for paper trading.
    Reports trade outcomes to orchestrator for River learning.
    """

    def __init__(self, account_balance: Decimal = Decimal("10000"), leverage: int = 10):
        self.executor = VirtualExecutor()
        self.account_balance = account_balance
        self.leverage = leverage
        self.on_trade_closed: Optional[Callable] = None
        self._active_decision: Optional[TradeDecision] = None
        self._trade_count = 0

    @property
    def open_trade(self):
        return self.executor.open_trade

    @property
    def trade_history(self):
        return self.executor.trade_history

    def execute_decision(self, decision: TradeDecision) -> bool:
        """Execute a TradeDecision as a real trade."""
        if not decision.should_trade:
            logger.debug(f"[EXECUTOR] Skipping rejected decision: {decision.rejection_reason}")
            return False

        if self.executor.open_trade is not None:
            logger.warning("[EXECUTOR] Already have open position, skipping")
            return False

        proposal = self._decision_to_proposal(decision)
        if proposal is None:
            return False

        auth_result = AuthorizationResult(
            proposal_id=proposal.id,
            authorized=True,
            reason="MULTI_TF_APPROVED",
            mode_at_decision="MODE2_FULL_REC",
            confidence_score=decision.confidence,
        )

        success = self.executor.execute_entry(
            proposal, auth_result,
            leverage=self.leverage,
            account_balance=self.account_balance,
        )

        if success:
            self._active_decision = decision
            self._trade_count += 1
            logger.info(
                f"[EXECUTOR] TRADE #{self._trade_count} | "
                f"{decision.direction} @ {decision.entry_zone_low}-{decision.entry_zone_high} | "
                f"Size={decision.position_size_pct}% | Conf={decision.confidence:.3f}"
            )

        return success

    def check_exit(self, current_price: float, timestamp: int) -> bool:
        """Check if current position should exit based on price action."""
        if self.executor.open_trade is None:
            return False

        trade = self.executor.open_trade
        exit_signal = None

        if self._active_decision and self._active_decision.stop_loss:
            sl = self._active_decision.stop_loss
            if trade.direction == Direction.BULLISH and current_price < sl:
                exit_signal = ExitSignal(
                    position_id=trade.classification_tag_hash,
                    trigger=ExitTrigger.EXIT_TRAILING_STOP,
                    exit_price=Decimal(str(sl)),
                    reason="STOP_LOSS_HIT",
                )
            elif trade.direction == Direction.BEARISH and current_price > sl:
                exit_signal = ExitSignal(
                    position_id=trade.classification_tag_hash,
                    trigger=ExitTrigger.EXIT_TRAILING_STOP,
                    exit_price=Decimal(str(sl)),
                    reason="STOP_LOSS_HIT",
                )

        if exit_signal is None and self._active_decision and self._active_decision.take_profit:
            tp = self._active_decision.take_profit
            if trade.direction == Direction.BULLISH and current_price >= tp:
                exit_signal = ExitSignal(
                    position_id=trade.classification_tag_hash,
                    trigger=ExitTrigger.EXIT_PARTIAL_TP,
                    exit_price=Decimal(str(tp)),
                    reason="TAKE_PROFIT_HIT",
                )
            elif trade.direction == Direction.BEARISH and current_price <= tp:
                exit_signal = ExitSignal(
                    position_id=trade.classification_tag_hash,
                    trigger=ExitTrigger.EXIT_PARTIAL_TP,
                    exit_price=Decimal(str(tp)),
                    reason="TAKE_PROFIT_HIT",
                )

        if exit_signal:
            return self._execute_exit(exit_signal, timestamp)

        return False

    def force_exit(self, reason: str, current_price: float, timestamp: int) -> bool:
        """Force exit current position."""
        if self.executor.open_trade is None:
            return False

        exit_signal = ExitSignal(
            position_id=self.executor.open_trade.classification_tag_hash,
            trigger=ExitTrigger.EXIT_TRAILING_STOP,
            exit_price=Decimal(str(current_price)),
            reason=f"FORCE_EXIT: {reason}",
        )
        return self._execute_exit(exit_signal, timestamp)

    def _execute_exit(self, exit_signal: ExitSignal, timestamp: int) -> bool:
        """Execute exit and report to River."""
        success = self.executor.execute_exit(exit_signal)

        if success:
            closed_trade = self.executor.trade_history[-1]
            pnl_pct = float(closed_trade.pnl_pct) if closed_trade.pnl_pct else 0.0

            if closed_trade.pnl_usd:
                self.account_balance += closed_trade.pnl_usd

            if self.on_trade_closed:
                self.on_trade_closed(pnl_pct, timestamp)

            logger.info(
                f"[EXECUTOR] EXIT | PnL={pnl_pct:+.2f}% | "
                f"Balance=${self.account_balance:.2f} | Reason={exit_signal.reason}"
            )

            self._active_decision = None

        return success

    def _decision_to_proposal(self, decision: TradeDecision) -> Optional[TradeProposal]:
        """Convert TradeDecision to TradeProposal for VirtualExecutor."""
        if not decision.entry_zone_low or not decision.entry_zone_high:
            logger.error("[EXECUTOR] Missing entry zone")
            return None

        if not decision.stop_loss:
            logger.error("[EXECUTOR] Missing stop loss")
            return None

        guard_id = decision.guard_line_id
        if not guard_id:
            logger.error("[EXECUTOR] BLOCKED: No real guard_line_id. Refusing fake ID.")
            return None

        entry_price = Decimal(str((decision.entry_zone_low + decision.entry_zone_high) / 2))
        stop_loss = Decimal(str(decision.stop_loss))
        direction = Direction.BULLISH if decision.direction == "BULLISH" else Direction.BEARISH

        risk_distance = abs(entry_price - stop_loss)
        risk_pct = (risk_distance / entry_price) * Decimal("100")

        return TradeProposal(
            id=f"MTF_{uuid.uuid4().hex[:8]}",
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=Decimal(str(decision.take_profit)) if decision.take_profit else None,
            risk_pct=risk_pct,
            support_line_id=guard_id,
            wave_id=None,
            classification_tag_hash=f"MTF_{decision.confluence.confluence_score:.3f}" if decision.confluence else "MTF_UNKNOWN",
        )

    def get_status(self) -> dict:
        return {
            "account_balance": float(self.account_balance),
            "open_trade": self.executor.open_trade is not None,
            "trade_count": self._trade_count,
            "trade_history_count": len(self.executor.trade_history),
            "last_trade_pnl": float(self.executor.trade_history[-1].pnl_pct) if self.executor.trade_history else None,
        }
