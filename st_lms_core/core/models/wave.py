"""
Wave Model. Represents structural movement between ST Lines.
Required by WaveBuilder, FibonacciCalculator, AdaptiveStack, and DualRiver.
"""
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from st_lms_core.core.models.enums import Direction


@dataclass
class Wave:
    id: str
    direction: Direction
    start_line_id: str
    end_line_id: str
    start_price: Decimal
    end_price: Decimal
    length_points: int
    amplitude: Decimal
    start_ts: int
    end_ts: Optional[int] = None

    @property
    def is_complete(self) -> bool:
        return self.end_ts is not None
