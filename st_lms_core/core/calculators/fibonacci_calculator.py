"""
Fibonacci Calculator - FINAL AUDITED VERSION (Fix #1b)
Passes wave direction to FibLevels.from_wave() for direction-aware calculation.
Entry zone check is now direction-agnostic (levels pre-normalized).
"""
from decimal import Decimal
from typing import Optional
from st_lms_core.core.models.fib_levels import FibLevels
from st_lms_core.core.models.wave import Wave


class FibonacciCalculator:
    @staticmethod
    def compute(wave: Optional[Wave]) -> Optional[FibLevels]:
        if wave is None or not wave.is_complete:
            return None
        return FibLevels.from_wave(
            wave.start_price, wave.end_price, wave.direction.value
        )

    @staticmethod
    def is_in_entry_zone(price: Decimal, fib: FibLevels) -> bool:
        """Direction-agnostic: level_382 and level_618 already normalized."""
        if fib is None:
            return False
        return fib.level_382 <= price <= fib.level_618
