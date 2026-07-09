"""
MACD Calculator - Computes MACD bucket classification.
Returns string for Dual River pattern matching. No signal generation.
"""
from decimal import Decimal
from collections import deque
from st_lms_core.config.settings import CONFIG


class MACDCalculator:
    def __init__(self):
        self._prices: deque[Decimal] = deque(maxlen=CONFIG.macd_slow + CONFIG.macd_signal)
        self._count: int = 0

    @property
    def is_ready(self) -> bool:
        return self._count >= CONFIG.macd_slow + CONFIG.macd_signal

    def calculate(self, close: Decimal) -> str:
        self._prices.append(close)
        self._count += 1
        if not self.is_ready:
            return "NEUTRAL"

        prices_list = list(self._prices)
        ema_fast = self._compute_ema(prices_list, CONFIG.macd_fast)
        ema_slow = self._compute_ema(prices_list, CONFIG.macd_slow)
        macd_line = ema_fast - ema_slow
        signal = self._compute_ema(prices_list[-CONFIG.macd_signal:], CONFIG.macd_signal)
        histogram = macd_line - signal

        return self._classify_bucket(macd_line, histogram)

    @staticmethod
    def _compute_ema(values: list[Decimal], period: int) -> Decimal:
        if len(values) < period:
            return values[-1] if values else Decimal("0")
        multiplier = Decimal("2") / Decimal(str(period + 1))
        ema = sum(values[:period]) / Decimal(str(period))
        for price in values[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    @staticmethod
    def _classify_bucket(macd_line: Decimal, histogram: Decimal) -> str:
        zero = Decimal("0")
        if macd_line > zero and histogram > zero:
            return "BULLISH"
        elif macd_line < zero and histogram < zero:
            return "BEARISH"
        elif (macd_line > zero and histogram < zero) or (macd_line < zero and histogram > zero):
            return "WEAKENING"
        return "NEUTRAL"

    def reset(self) -> None:
        self._prices.clear()
        self._count = 0
