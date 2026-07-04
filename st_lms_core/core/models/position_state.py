"""
Position State Model. Tracks enhanced exit logic: trailing stop, partial TP, touch counters.
Persisted via PositionRepository with dirty flag pattern.
"""
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field
from st_lms_core.core.models.enums import Direction


@dataclass
class PositionState:
    position_id: str
    direction: Direction
    guard_line_id: str
    entry_price: Decimal
    fib_levels: object

    break_detected_ts: Optional[int] = None
    retouched_after_break: bool = False
    touch_count_after_break: int = 0
    single_touch_detected: bool = False
    retouched_after_single: bool = False
    partial_tp_taken: bool = False
    trailing_stop_level: Decimal = field(default_factory=lambda: Decimal("0"))
    best_price_since_entry: Decimal = field(default_factory=lambda: Decimal("0"))

    def __post_init__(self):
        if self.trailing_stop_level == Decimal("0"):
            self.trailing_stop_level = self.entry_price
        if self.best_price_since_entry == Decimal("0"):
            self.best_price_since_entry = self.entry_price
