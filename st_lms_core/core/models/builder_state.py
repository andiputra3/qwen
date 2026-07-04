"""
Builder State Model. Stateful tracking for Supertrend Line construction.
Used exclusively by STLineBuilder to maintain continuity across candles.
"""
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from st_lms_core.core.models.enums import Direction
from st_lms_core.core.models.supertrend_line import SupertrendLine


@dataclass
class BuilderState:
    current_line: Optional[SupertrendLine] = None
    prev_st_point: Decimal = Decimal("0")
    prev_direction: Optional[Direction] = None
    flip_count: int = 0
    last_flip_ts: Optional[int] = None

    @property
    def has_active_line(self) -> bool:
        return self.current_line is not None

    @property
    def is_warmup_complete(self) -> bool:
        return self.prev_direction is not None
