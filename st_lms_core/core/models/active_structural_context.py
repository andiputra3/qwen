"""
Active Structural Context - Output of Adaptive Stack (Living Memory Selector).
Contains ALL historically relevant structures that are still alive at current price.
Replaces ActiveStructureSet which was a geometric evaluator, not a memory selector.
"""
from decimal import Decimal
from typing import List, Optional
from dataclasses import dataclass, field
from st_lms_core.core.models.supertrend_line import SupertrendLine
from st_lms_core.core.models.wave import Wave


@dataclass
class ActiveStructuralContext:
    living_support_lines: List[SupertrendLine] = field(default_factory=list)
    living_resistance_lines: List[SupertrendLine] = field(default_factory=list)
    relevant_waves: List[Wave] = field(default_factory=list)
    nearest_support: Optional[SupertrendLine] = None
    nearest_resistance: Optional[SupertrendLine] = None
    total_living_lines: int = 0
    timestamp: int = 0

    @property
    def has_structure(self) -> bool:
        return self.total_living_lines > 0

    @property
    def corridor_width(self) -> Optional[Decimal]:
        if self.nearest_support and self.nearest_resistance:
            return abs(self.nearest_resistance.price_level - self.nearest_support.price_level)
        return None
