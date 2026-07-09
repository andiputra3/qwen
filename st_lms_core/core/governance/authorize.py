"""
Enhanced Authorize Gateway - FINAL AUDITED VERSION (Fix #3)
Fib zone check now uses normalized levels (direction-agnostic).
Sideway check uses MarketState classification, NOT ATR.
All 7 verification layers preserved.
"""
from decimal import Decimal
from typing import Optional
import logging

from st_lms_core.config.settings import CONFIG
from st_lms_core.core.models.trade import TradeProposal, AuthorizationResult
from st_lms_core.core.models.context import ContextSynthesis
from st_lms_core.core.models.enums import Direction, RiverMode
from st_lms_core.core.models.active_structural_context import ActiveStructuralContext
from st_lms_core.core.models.fib_levels import FibLevels
from st_lms_core.core.intelligence.dual_river_engine import DualRiverEngine

logger = logging.getLogger(__name__)


class AuthorizeGateway:
    def __init__(self, dual_river: DualRiverEngine):
        self._river = dual_river

    def evaluate(self, proposal: TradeProposal, active_context: ActiveStructuralContext,
                 context: ContextSynthesis, fib_levels: Optional[FibLevels]) -> AuthorizationResult:
        # LAYER 1: Structure Alignment
        if not self._check_structure_alignment(proposal, active_context):
            return self._reject(proposal, "STRUCTURE_MISALIGNMENT")

        # LAYER 2: Sideway Check (CONSTITUTIONAL: structural classification, NOT ATR)
        if context.is_sideway:
            return self._reject(proposal, "INSIDE_SIDEWAY_STRUCTURE")

        # LAYER 3: Risk Limit
        if proposal.risk_pct > CONFIG.max_risk_per_trade_pct:
            return self._reject(proposal, f"RISK_EXCEEDED ({proposal.risk_pct} > {CONFIG.max_risk_per_trade_pct})")

        # LAYER 4: Fibonacci Zone Entry (Direction-agnostic via normalized levels)
        if fib_levels is not None:
            if not self._check_fib_zone(proposal, fib_levels):
                return self._reject(proposal, f"PRICE_NOT_IN_FIB_ZONE (price={proposal.entry_price}, zone={fib_levels.level_382}-{fib_levels.level_618})")
        else:
            return self._reject(proposal, "NO_FIB_LEVELS_AVAILABLE")

        # LAYER 5: MACD Confirmation Gate
        if not self._check_macd_gate(proposal.direction, context.macd_state):
            return self._reject(proposal, f"MACD_REJECTED ({context.macd_state})")

        # LAYER 6: OI Confirmation Gate (Graceful)
        if context.oi_available:
            if not self._check_oi_gate(proposal.direction, context.oi_state):
                return self._reject(proposal, f"OI_REJECTED ({context.oi_state})")

        # LAYER 7: Dual River Adaptive Gate
        river_context = {
            "st_direction": proposal.direction.value,
            "wave_direction": context.wave_direction or "",
            "wave_length": context.wave_length,
            "stack_priority": context.stack_priority,
            "compressed": context.compressed,
            "macd": context.macd_state,
            "oi_state": context.oi_state or "ABSENT"
        }
        rec = self._river.get_entry_recommendation(river_context)
        if not rec["should_enter"]:
            return self._reject(proposal, f"RIVER_REJECTED (Conf={rec['confidence']:.3f})")

        logger.info(f"[AUTHORIZE] APPROVED | Fib=OK MACD={context.macd_state} OI={context.oi_state or 'ABSENT'} RiverConf={rec['confidence']:.3f}")
        return AuthorizationResult(
            proposal_id=proposal.id, authorized=True, reason="APPROVED",
            mode_at_decision=RiverMode.MODE1_COLD_START.value, confidence_score=rec["confidence"]
        )

    @staticmethod
    def _check_structure_alignment(proposal, active_context):
        if proposal.direction == Direction.BULLISH:
            return active_context.nearest_support is not None
        return active_context.nearest_resistance is not None

    @staticmethod
    def _check_fib_zone(proposal, fib):
        """Direction-agnostic: levels already normalized in FibLevels.from_wave()."""
        return fib.level_382 <= proposal.entry_price <= fib.level_618

    @staticmethod
    def _check_macd_gate(direction, macd_state):
        if direction == Direction.BULLISH:
            return macd_state in ("BULLISH", "WEAKENING")
        return macd_state in ("BEARISH", "WEAKENING")

    @staticmethod
    def _check_oi_gate(direction, oi_state):
        if oi_state is None:
            return True
        return oi_state != "DECREASING"

    @staticmethod
    def _reject(proposal, reason):
        logger.warning(f"[AUTHORIZE] REJECTED | {reason} | ID={proposal.id[:8]}")
        return AuthorizationResult(
            proposal_id=proposal.id, authorized=False,
            reason=reason, mode_at_decision="", confidence_score=0.0
        )
