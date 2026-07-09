"""
Candle Model - Primary data structure for ST-LMS Pipeline.
Supports OHLC + ST Point + MACD + OI (native 5m alignment).
"""
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass


@dataclass
class Candle:
    timestamp: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    st_point: Decimal
    macd_value: Decimal
    oi_value: Optional[Decimal] = None

    @property
    def has_oi(self) -> bool:
        return self.oi_value is not None
