"""
Context Synthesizer - FINAL AUDITED VERSION (Fix #5)
Quality-aware stack_priority based on line validity + wave relevance.
Chaotic lines no longer inflate priority artificially.
Compressed derived from StructuralForm, NOT ATR.
"""
from decimal import Decimal
from typing import Optional
import logging

from st_lms_core.core.models.context import ContextSynthesis
from st_lms_core.core.models.active_structural_context import ActiveStructuralContext
from st_lms_core.core.models.market_state import MarketState, StructuralForm
from st_lms_core.core.models.wave import Wave

logger = logging.getLogger(__name__)


class ContextSynthesizer:
    def synthesize(
        self, timestamp: int, price: Decimal,
        market_state: MarketState, structural_form: StructuralForm,
        last_wave: Optional[Wave], active_context: ActiveStructuralContext,
        macd_bucket: str, oi_state: str, velocity_regime: str
    ) -> ContextSynthesis:
        wave_dir = last_wave.direction.value if last_wave else None
        wave_len = last_wave.length_points if last_wave else 0

        support_price = (
            active_context.nearest_support.price_level
            if active_context.nearest_support else None
        )
        resistance_price = (
            active_context.nearest_resistance.price_level
            if active_context.nearest_resistance else None
        )

        is_compressed = structural_form in (
            StructuralForm.CONVERGING, StructuralForm.FLAT_CORRIDOR
        )

        all_lines = active_context.living_support_lines + active_context.living_resistance_lines
        valid_lines = sum(1 for l in all_lines if l.is_valid)
        relevant_waves = len(active_context.relevant_waves)
        total_living = active_context.total_living_lines

        weighted_score = (valid_lines * 2) + relevant_waves + (total_living * Decimal("0.5"))

        if weighted_score >= 8:
            stack_priority = "HIGH"
        elif weighted_score >= 4:
            stack_priority = "MEDIUM"
        else:
            stack_priority = "LOW"

        ctx = ContextSynthesis(
            timestamp=timestamp, price=price,
            trend_state=market_state.value,
            wave_direction=wave_dir, wave_length=wave_len,
            compressed=is_compressed, macd_state=macd_bucket,
            oi_state=oi_state, stack_priority=stack_priority,
            active_support_price=support_price,
            active_resistance_price=resistance_price
        )

        logger.debug(
            f"[CONTEXT] State={market_state.value} Form={structural_form.value} "
            f"Stack={stack_priority}(score={weighted_score:.1f}) Compressed={is_compressed}"
        )
        return ctx
