"""
Supertrend Line Model.
Constitutional: MUST be flat horizontal. No slope/angle properties.
Preserve All: Deactivated lines are NEVER deleted.
"""
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from st_lms_core.core.models.enums import Direction, LineStatus


@dataclass
class SupertrendLine:
    id: str
    direction: Direction
    price_level: Decimal
    start_ts: int
    end_ts: Optional[int] = None
    point_count: int = 0
    status: LineStatus = LineStatus.PENDING

    @property
    def is_valid(self) -> bool:
        return self.status == LineStatus.VALID

    @property
    def is_pending(self) -> bool:
        return self.status == LineStatus.PENDING

    @property
    def is_active(self) -> bool:
        return self.status in (LineStatus.PENDING, LineStatus.VALID)

    def validate(self) -> None:
        if self.status == LineStatus.PENDING:
            self.status = LineStatus.VALID

    def deactivate(self, ts: int, never_valid: bool = False) -> None:
        self.end_ts = ts
        self.status = LineStatus.NEVER_VALID if never_valid else LineStatus.DEACTIVATED
