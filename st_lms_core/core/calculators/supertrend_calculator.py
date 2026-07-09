"""
Supertrend Calculator - Computes ST Point from OHLC.
Constitutional: ST Point calculated INSIDE pipeline. Locked ATR(10), Mult(3).
Exposes is_warmup_complete for external validation.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from st_lms_core.config.settings import CONFIG


class SupertrendCalculator:
    def __init__(self):
        self._tr_buffer: list[Decimal] = []
        self._prev_close: Optional[Decimal] = None
        self._prev_upper: Decimal = Decimal("0")
        self._prev_lower: Decimal = Decimal("0")
        self._prev_dir: int = 1
        self._warmup_count: int = 0

    @property
    def is_warmup_complete(self) -> bool:
        return self._warmup_count >= CONFIG.st_period

    def calculate(self, high: Decimal, low: Decimal, close: Decimal) -> Optional[Decimal]:
        if self._prev_close is None:
            self._prev_close = close
            self._warmup_count += 1
            return None

        tr = max(high - low, abs(high - self._prev_close), abs(low - self._prev_close))
        self._tr_buffer.append(tr)
        self._warmup_count += 1

        if len(self._tr_buffer) < CONFIG.st_period:
            self._prev_close = close
            return None

        atr = sum(self._tr_buffer[-CONFIG.st_period:]) / Decimal(str(CONFIG.st_period))
        hl2 = (high + low) / Decimal("2")
        basic_upper = hl2 + CONFIG.st_multiplier * atr
        basic_lower = hl2 - CONFIG.st_multiplier * atr

        final_upper = min(basic_upper, self._prev_upper) if self._prev_close <= self._prev_upper else basic_upper
        final_lower = max(basic_lower, self._prev_lower) if self._prev_close >= self._prev_lower else basic_lower

        if self._prev_dir == 1:
            st_point = final_upper if close < final_lower else final_lower
            new_dir = -1 if close < final_lower else 1
        else:
            st_point = final_lower if close > final_upper else final_upper
            new_dir = 1 if close > final_upper else -1

        self._prev_upper = final_upper
        self._prev_lower = final_lower
        self._prev_dir = new_dir
        self._prev_close = close

        return st_point.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def reset(self) -> None:
        self._tr_buffer.clear()
        self._prev_close = None
        self._prev_upper = Decimal("0")
        self._prev_lower = Decimal("0")
        self._prev_dir = 1
        self._warmup_count = 0
