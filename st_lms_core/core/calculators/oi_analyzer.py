"""
Open Interest Analyzer - Classifies OI state from sequential values.
Handles OI ABSENT gracefully for Dual River learning.
"""
from decimal import Decimal
from typing import Optional
from st_lms_core.core.models.enums import OIState


class OIAnalyzer:
    INCREASING_THRESHOLD = Decimal("0.3")
    DECREASING_THRESHOLD = Decimal("-0.3")

    def __init__(self):
        self._prev_oi: Optional[Decimal] = None

    def classify(self, current_oi: Optional[Decimal]) -> str:
        if current_oi is None:
            return OIState.ABSENT.value
        if self._prev_oi is None or self._prev_oi == Decimal("0"):
            self._prev_oi = current_oi
            return OIState.FLAT.value

        pct_change = ((current_oi - self._prev_oi) / self._prev_oi) * Decimal("100")
        self._prev_oi = current_oi

        if pct_change > self.INCREASING_THRESHOLD:
            return OIState.INCREASING.value
        elif pct_change < self.DECREASING_THRESHOLD:
            return OIState.DECREASING.value
        return OIState.FLAT.value

    def reset(self) -> None:
        self._prev_oi = None
