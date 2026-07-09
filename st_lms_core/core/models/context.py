"""
Context & Classification Models.
trend_state carries MarketState value (UPTREND/DOWNTREND/SIDEWAY).
compressed derived from StructuralForm, not ATR.
stack_priority derived from quality-weighted living line count.
"""
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass


@dataclass
class ContextSynthesis:
    timestamp: int
    price: Decimal
    trend_state: str
    wave_direction: Optional[str]
    wave_length: int
    compressed: bool
    macd_state: str
    oi_state: Optional[str]
    stack_priority: str
    active_support_price: Optional[Decimal]
    active_resistance_price: Optional[Decimal]

    @property
    def oi_available(self) -> bool:
        return self.oi_state is not None and self.oi_state != "ABSENT"

    @property
    def is_sideway(self) -> bool:
        """Sideway = structural classification result, NOT ATR threshold."""
        return self.trend_state == "SIDEWAY"


@dataclass
class ClassificationTag:
    hash_key: str
    trend_label: str
    velocity_regime: str
    compressed: bool
    macd_bucket: str
    oi_bucket: str
    wave_length_bucket: str
    stack_priority: str
