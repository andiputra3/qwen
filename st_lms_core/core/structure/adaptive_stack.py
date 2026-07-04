"""
Adaptive Stack - FINAL AUDITED VERSION (Constitutional + Fix #4)
Living Structure Selector with ATR-relative invalidation tolerance.
Prevents premature structure death from normal 5m noise wicks.

DEFINISI RESMI:
- Adaptive Stack adalah sistem yang memilih struktur historis yang masih relevan.
- Adaptive Stack BUKAN AI, BUKAN Optimizer, BUKAN Dynamic Parameter.
- Adaptive Stack bertanya: "Struktur mana yang masih hidup?"
- Adaptive Stack TIDAK memahami pasar. Ia hanya memilih memori yang masih berlaku.
"""
from decimal import Decimal
from typing import List, Optional
import logging

from st_lms_core.core.models.supertrend_line import SupertrendLine
from st_lms_core.core.models.wave import Wave
from st_lms_core.core.models.active_structural_context import ActiveStructuralContext
from st_lms_core.core.models.enums import Direction

logger = logging.getLogger(__name__)


class AdaptiveStack:
    INVALIDATION_ATR_MULTIPLIER = Decimal("1.5")
    FALLBACK_TOLERANCE_PCT = Decimal("0.005")
    MAX_LIVING_PER_DIRECTION = 5

    def select_living_structures(
        self, all_lines: List[SupertrendLine], all_waves: List[Wave],
        current_price: Decimal, current_ts: int,
        current_atr: Optional[Decimal] = None
    ) -> ActiveStructuralContext:
        living_support = self._select_living_lines(all_lines, current_price, Direction.BULLISH, current_atr)
        living_resistance = self._select_living_lines(all_lines, current_price, Direction.BEARISH, current_atr)

        living_line_ids = {l.id for l in living_support + living_resistance}
        relevant_waves = [
            w for w in all_waves if w.is_complete and w.end_line_id in living_line_ids
        ]

        nearest_support = min(
            living_support, key=lambda l: abs(l.price_level - current_price), default=None
        ) if living_support else None

        nearest_resistance = min(
            living_resistance, key=lambda l: abs(l.price_level - current_price), default=None
        ) if living_resistance else None

        context = ActiveStructuralContext(
            living_support_lines=living_support,
            living_resistance_lines=living_resistance,
            relevant_waves=relevant_waves,
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            total_living_lines=len(living_support) + len(living_resistance),
            timestamp=current_ts
        )

        logger.debug(
            f"[ADAPTIVE-STACK] Selected {context.total_living_lines} living | "
            f"S={len(living_support)} R={len(living_resistance)} W={len(relevant_waves)}"
        )
        return context

    def _select_living_lines(
        self, all_lines: List[SupertrendLine], current_price: Decimal,
        direction: Direction, current_atr: Optional[Decimal]
    ) -> List[SupertrendLine]:
        living = []

        if current_atr and current_atr > Decimal("0"):
            tolerance = current_atr * self.INVALIDATION_ATR_MULTIPLIER
        else:
            tolerance = current_price * self.FALLBACK_TOLERANCE_PCT

        for line in all_lines:
            if line.direction != direction or not line.is_active:
                continue
            if direction == Direction.BULLISH:
                if current_price < (line.price_level - tolerance):
                    continue
            else:
                if current_price > (line.price_level + tolerance):
                    continue
            living.append(line)

        living.sort(key=lambda l: abs(l.price_level - current_price))
        return living[:self.MAX_LIVING_PER_DIRECTION]

    def reset(self) -> None:
        pass
