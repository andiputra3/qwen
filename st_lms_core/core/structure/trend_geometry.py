"""
Trend Geometry - Structural Form Analyzer (CONSTITUTIONAL)

TANGGUNG JAWAB: Menganalisis BENTUK GEOMETRI struktur aktif.
TIDAK BERTANGGUNG JAWAB: Mengklasifikasikan market state, menggunakan ATR/indikator.
SIDEWAY DETECTION: Converging/Flat corridor detected HERE, classified in TrendClassifier.
"""
from decimal import Decimal
import logging

from st_lms_core.core.models.active_structural_context import ActiveStructuralContext
from st_lms_core.core.models.market_state import StructuralForm

logger = logging.getLogger(__name__)


class TrendGeometry:
    MIN_STAIR_STEP_PCT = Decimal("0.002")
    CONVERGENCE_RATIO = Decimal("0.7")

    def analyze(self, context: ActiveStructuralContext) -> StructuralForm:
        supports = context.living_support_lines
        resistances = context.living_resistance_lines
        total = context.total_living_lines

        if total == 0:
            return StructuralForm.NO_STRUCTURE
        if len(supports) == 0 or len(resistances) == 0:
            return StructuralForm.SINGLE_DIRECTION
        if total >= 6 and self._is_chaotic(supports, resistances):
            return StructuralForm.CHAOTIC
        if self._is_converging(supports, resistances):
            return StructuralForm.CONVERGING
        if self._is_flat_corridor(supports, resistances):
            return StructuralForm.FLAT_CORRIDOR

        stair_type = self._detect_stairs(supports, resistances)
        if stair_type is not None:
            return stair_type

        return StructuralForm.CHAOTIC

    def _is_chaotic(self, supports: list, resistances: list) -> bool:
        all_prices = sorted([l.price_level for l in supports] + [l.price_level for l in resistances])
        if len(all_prices) < 4:
            return False
        prev_dir = None
        switches = 0
        for price in all_prices:
            is_sup = any(abs(l.price_level - price) < Decimal("0.01") for l in supports)
            cur = "S" if is_sup else "R"
            if prev_dir and cur != prev_dir:
                switches += 1
            prev_dir = cur
        return switches >= 3

    def _is_converging(self, supports: list, resistances: list) -> bool:
        if len(supports) < 2 or len(resistances) < 2:
            return False
        sup_sorted = sorted(supports, key=lambda l: l.start_ts)
        res_sorted = sorted(resistances, key=lambda l: l.start_ts)
        oldest_gap = abs(res_sorted[0].price_level - sup_sorted[0].price_level)
        newest_gap = abs(res_sorted[-1].price_level - sup_sorted[-1].price_level)
        if oldest_gap == Decimal("0"):
            return False
        return (newest_gap / oldest_gap) < self.CONVERGENCE_RATIO

    def _is_flat_corridor(self, supports: list, resistances: list) -> bool:
        if not supports or not resistances:
            return False
        sup_spread = max(l.price_level for l in supports) - min(l.price_level for l in supports)
        res_spread = max(l.price_level for l in resistances) - min(l.price_level for l in resistances)
        corridor = abs(resistances[0].price_level - supports[0].price_level)
        if corridor == Decimal("0"):
            return False
        return (sup_spread / corridor) < Decimal("0.1") and (res_spread / corridor) < Decimal("0.1")

    def _detect_stairs(self, supports: list, resistances: list):
        if len(supports) >= 2:
            sorted_sup = sorted(supports, key=lambda l: l.start_ts)
            steps_up = sum(
                1 for i in range(len(sorted_sup) - 1)
                if sorted_sup[i+1].price_level > sorted_sup[i].price_level * (1 + self.MIN_STAIR_STEP_PCT)
            )
            if steps_up >= len(sorted_sup) - 1:
                return StructuralForm.ASCENDING_STAIRS
        if len(resistances) >= 2:
            sorted_res = sorted(resistances, key=lambda l: l.start_ts)
            steps_down = sum(
                1 for i in range(len(sorted_res) - 1)
                if sorted_res[i+1].price_level < sorted_res[i].price_level * (1 - self.MIN_STAIR_STEP_PCT)
            )
            if steps_down >= len(sorted_res) - 1:
                return StructuralForm.DESCENDING_STAIRS
        return None

    def reset(self) -> None:
        pass
