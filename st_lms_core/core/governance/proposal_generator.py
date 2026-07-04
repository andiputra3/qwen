"""
Trade Proposal Generator - FINAL AUDITED VERSION (Fix #2)
LONG: Enter at discount (level_382). SHORT: Enter at premium (level_618).
Risk calculated from distance to guard line (support/resistance).
"""
from decimal import Decimal
from typing import Optional
import uuid, logging

from st_lms_core.config.settings import CONFIG
from st_lms_core.core.models.trade import TradeProposal
from st_lms_core.core.models.context import ContextSynthesis
from st_lms_core.core.models.active_structural_context import ActiveStructuralContext
from st_lms_core.core.models.fib_levels import FibLevels
from st_lms_core.core.models.enums import Direction

logger = logging.getLogger(__name__)


class ProposalGenerator:
    def generate(self, context: ContextSynthesis, active_context: ActiveStructuralContext,
                 fib_levels: Optional[FibLevels], tag_hash: str) -> Optional[TradeProposal]:
        if fib_levels is None:
            return None

        if context.wave_direction == Direction.BULLISH.value:
            direction = Direction.BULLISH
            entry_price = fib_levels.level_382
            stop_loss = active_context.nearest_support.price_level if active_context.nearest_support else fib_levels.level_000
            guard_line_id = active_context.nearest_support.id if active_context.nearest_support else ""
        elif context.wave_direction == Direction.BEARISH.value:
            direction = Direction.BEARISH
            entry_price = fib_levels.level_618
            stop_loss = active_context.nearest_resistance.price_level if active_context.nearest_resistance else fib_levels.level_000
            guard_line_id = active_context.nearest_resistance.id if active_context.nearest_resistance else ""
        else:
            return None

        if not guard_line_id:
            return None

        risk_distance = abs(entry_price - stop_loss)
        if risk_distance == Decimal("0"):
            return None
        risk_pct = (risk_distance / entry_price) * Decimal("100")

        proposal = TradeProposal(
            id=f"PRP_{uuid.uuid4().hex[:8]}", direction=direction,
            entry_price=entry_price, stop_loss=stop_loss, take_profit=None,
            risk_pct=risk_pct, support_line_id=guard_line_id,
            wave_id=None, classification_tag_hash=tag_hash
        )
        logger.debug(f"[PROPOSAL] {direction.name} Entry={entry_price:.2f} SL={stop_loss:.2f} Risk={risk_pct:.2f}%")
        return proposal
