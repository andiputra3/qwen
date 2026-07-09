"""
Adaptive Orchestrator - CRASH-FIXED VERSION (P0-1)
Fix: _last_proposal initialized in __init__ and reset at start of process_candle.
Fix #1: Complete Exit Execution (executor.execute_exit + account update)
Fix #2 Integration: Passes account_balance to executor for correct sizing
Mode Filter: Enforces LONG_ONLY / SHORT_ONLY / SIDEWAY_ONLY isolation.
"""
from decimal import Decimal
from typing import Optional, List
import logging

from st_lms_core.core.pipeline.orchestrator import STLMSPipeline
from st_lms_core.core.intelligence.dual_river_engine import DualRiverEngine
from st_lms_core.core.governance.authorize import AuthorizeGateway
from st_lms_core.core.governance.exit_monitor import ExitMonitor
from st_lms_core.core.governance.proposal_generator import ProposalGenerator
from st_lms_core.core.risk.risk_manager import RiskManager
from st_lms_core.repository.position_repository import PositionRepository
from st_lms_core.execution.virtual_executor import VirtualExecutor
from st_lms_core.core.models.position_state import PositionState
from st_lms_core.core.models.enums import Direction, ExitTrigger

logger = logging.getLogger(__name__)


class AdaptiveSTLMSPipeline(STLMSPipeline):
    def __init__(self, account_balance: Decimal = Decimal("10000"),
                 allowed_modes: Optional[List[str]] = None):
        super().__init__()
        self._account_balance = account_balance
        self._allowed_modes = allowed_modes or ["LONG_ONLY", "SHORT_ONLY", "SIDEWAY_ONLY"]
        self.dual_river = DualRiverEngine()
        self._authorize = AuthorizeGateway(self.dual_river)
        self._exit_monitor = ExitMonitor()
        self._proposal_gen = ProposalGenerator()
        self._risk_manager = RiskManager()
        self._position_repo = PositionRepository()
        self.executor = VirtualExecutor()
        self._active_position: Optional[PositionState] = None
        self._trade_counter = 0
        self._position_dirty: bool = False

        self._last_proposal = None

        restored = self._position_repo.load()
        if restored:
            self._active_position = restored
            self._risk_manager.on_position_opened()
            logger.info(f"[ORCHESTRATOR] Restored position: {restored.position_id[:8]}")

    def _mark_position_dirty(self):
        self._position_dirty = True

    def _flush_position_if_dirty(self):
        if self._position_dirty:
            self._position_repo.save(self._active_position)
            self._position_dirty = False

    def process_candle(self, candle, macd_state="NEUTRAL", oi_state=None):
        self._last_proposal = None

        audit = super().process_candle(candle, macd_state, oi_state)
        if audit is None:
            return None

        for tid in list(self.dual_river._active_trades.keys()):
            self.dual_river.on_price_update(tid, candle.high, candle.low)

        # === EXIT EVALUATION ===
        if self._active_position is not None:
            guard_line = next(
                (l for l in self._line_builder.all_lines
                 if l.id == self._active_position.guard_line_id), None
            )
            if guard_line:
                valid_lines = [l for l in self._line_builder.all_lines if l.is_valid]
                exit_signal = self._exit_monitor.evaluate(
                    self._active_position, candle.close,
                    candle.low, candle.high, guard_line,
                    candle.timestamp, latest_valid_lines=valid_lines
                )
                if exit_signal:
                    audit["exit"] = exit_signal.trigger.value
                    audit["exit_price"] = float(exit_signal.exit_price)
                    audit["exit_reason"] = exit_signal.reason
                    self._mark_position_dirty()

                    if self.executor.open_trade is not None:
                        self.executor.execute_exit(exit_signal)
                        closed = self.executor.trade_history[-1]
                        if closed.pnl_usd is not None:
                            self._account_balance += closed.pnl_usd
                            self._risk_manager.record_trade_pnl(closed.pnl_usd)

                    for tid in list(self.dual_river._active_trades.keys()):
                        t = self.dual_river._active_trades[tid]
                        self.dual_river.on_exit(
                            trade_id=tid, exit_trigger=exit_signal.trigger.value,
                            exit_price=candle.close, macd_now=self._last_macd,
                            oi_now=self._last_oi or "ABSENT",
                            st_break="BROKEN" if "STOP" in exit_signal.trigger.value else "INTACT",
                            timestamp=candle.timestamp
                        )
                        break

                    if exit_signal.trigger != ExitTrigger.EXIT_PARTIAL_TP:
                        self._active_position = None
                        self._position_repo.save(None)
                        self._position_dirty = False
                        self._risk_manager.on_position_closed()

        # === ENTRY EVALUATION WITH MODE FILTER ===
        if self._active_position is None and hasattr(self, '_last_context'):
            wave_dir = self._last_context.wave_direction
            is_compressed = self._last_context.compressed

            if "LONG_ONLY" in self._allowed_modes and "SHORT_ONLY" not in self._allowed_modes:
                if wave_dir != "BULLISH":
                    self._flush_position_if_dirty()
                    return audit
            elif "SHORT_ONLY" in self._allowed_modes and "LONG_ONLY" not in self._allowed_modes:
                if wave_dir != "BEARISH":
                    self._flush_position_if_dirty()
                    return audit
            elif "SIDEWAY_ONLY" in self._allowed_modes and len(self._allowed_modes) == 1:
                if not is_compressed:
                    self._flush_position_if_dirty()
                    return audit

            proposal = self._proposal_gen.generate(
                self._last_context, self._last_active_context,
                self._last_fib, self._last_tag.hash_key
            )

            if proposal:
                risk_ok, risk_reason = self._risk_manager.validate_entry(
                    proposal, self._account_balance
                )
                self._last_proposal = proposal

                if not risk_ok:
                    audit["auth"] = f"RISK_REJECTED: {risk_reason}"
                else:
                    auth_result = self._authorize.evaluate(
                        proposal, self._last_active_context,
                        self._last_context, self._last_fib
                    )
                    audit["auth"] = auth_result.reason
                    audit["auth_confidence"] = auth_result.confidence_score

                    if auth_result.authorized:
                        self._trade_counter += 1
                        tid = f"TRD_{self._trade_counter}_{candle.timestamp}"

                        river_context = {
                            "st_direction": proposal.direction.value,
                            "wave_direction": self._last_context.wave_direction or "",
                            "wave_length": self._last_context.wave_length,
                            "stack_priority": self._last_context.stack_priority,
                            "compressed": self._last_context.compressed,
                            "macd": self._last_macd,
                            "oi_state": self._last_oi or "ABSENT",
                            "confidence": auth_result.confidence_score
                        }
                        self.dual_river.on_entry(tid, river_context, candle.close, candle.timestamp)

                        success = self.executor.execute_entry(
                            proposal, auth_result,
                            leverage=10, account_balance=self._account_balance
                        )
                        if success:
                            guard_id = (
                                self._last_active_context.nearest_support.id
                                if proposal.direction == Direction.BULLISH
                                else self._last_active_context.nearest_resistance.id
                            )
                            self._active_position = PositionState(
                                position_id=tid, direction=proposal.direction,
                                guard_line_id=guard_id or "", entry_price=candle.close,
                                fib_levels=self._last_fib
                            )
                            self._mark_position_dirty()
                            self._risk_manager.on_position_opened()

                            audit["entry"] = True
                            audit["entry_price"] = float(candle.close)
                            audit["direction"] = proposal.direction.value

        audit["river_records"] = self.dual_river.entry_river.total_records
        audit["active_trades"] = len(self.dual_river._active_trades)
        audit["balance"] = float(self._account_balance)
        self._flush_position_if_dirty()
        return audit

    def get_learning_summary(self):
        return self.dual_river.get_learning_summary()
