"""
Volatility Calculator - Computes ATR and velocity regime classification.
Used by TrendGeometry (indirectly via wave amplitude) and ContextSynthesizer.
ATR is for volatility measurement ONLY, never for sideway detection.
"""
from decimal import Decimal
from typing import Optional
from collections import deque


class VolatilityCalculator:
    def __init__(self, period: int = 14):
        self._period = period
        self._tr_buffer: deque[Decimal] = deque(maxlen=period)
        self._atr: Optional[Decimal] = None
        self._prev_close: Optional[Decimal] = None

    @property
    def current_atr(self) -> Optional[Decimal]:
        return self._atr

    def update(self, high: Decimal, low: Decimal, close: Decimal) -> Optional[Decimal]:
        if self._prev_close is None:
            self._prev_close = close
            return None

        tr = max(high - low, abs(high - self._prev_close), abs(low - self._prev_close))
        self._tr_buffer.append(tr)
        self._prev_close = close

        if len(self._tr_buffer) < self._period:
            return None

        self._atr = sum(self._tr_buffer) / Decimal(str(self._period))
        return self._atr

    def classify_velocity(self, wave_length: int, wave_amplitude: Decimal) -> str:
        if self._atr is None or self._atr == Decimal("0"):
            return "NORMAL_FLOW"
        ratio = float(wave_amplitude / self._atr)
        if ratio > 3.0 and wave_length <= 5:
            return "FAST_IMPULSE"
        elif ratio < 1.0 or wave_length > 15:
            return "SLOW_DRIFT"
        return "NORMAL_FLOW"

    def reset(self) -> None:
        self._tr_buffer.clear()
        self._atr = None
        self._prev_close = None
