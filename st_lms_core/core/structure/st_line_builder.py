"""
Supertrend Line Builder - Constructs flat horizontal ST Lines from ST Points.
Constitutional: Lines MUST be flat horizontal. Preserve All: never delete lines.
Stateful across candles using BuilderState.
"""
from decimal import Decimal
from typing import Optional, List
import uuid
import logging

from st_lms_core.config.settings import CONFIG
from st_lms_core.core.models.enums import Direction, LineStatus
from st_lms_core.core.models.supertrend_line import SupertrendLine
from st_lms_core.core.models.builder_state import BuilderState

logger = logging.getLogger(__name__)


class STLineBuilder:
    def __init__(self):
        self._state = BuilderState()
        self._all_lines: List[SupertrendLine] = []

    @property
    def all_lines(self) -> List[SupertrendLine]:
        return list(self._all_lines)

    @property
    def current_line(self) -> Optional[SupertrendLine]:
        return self._state.current_line

    def process_st_point(
        self, st_point: Decimal, close: Decimal, timestamp: int
    ) -> Optional[SupertrendLine]:
        if st_point == Decimal("0"):
            return None

        current_dir = Direction.BEARISH if st_point > close else Direction.BULLISH

        if not self._state.has_active_line:
            new_line = self._create_line(current_dir, st_point, timestamp)
            self._state.current_line = new_line
            self._state.prev_direction = current_dir
            self._state.prev_st_point = st_point
            self._all_lines.append(new_line)
            logger.info(f"[ST-BUILDER] Initial line: {current_dir.name} @ {st_point}")
            return None

        if current_dir != self._state.prev_direction:
            old_line = self._state.current_line
            if old_line:
                never_valid = old_line.point_count < CONFIG.st_line_min_points
                old_line.deactivate(timestamp, never_valid=never_valid)
                status = "NEVER_VALID" if never_valid else "DEACTIVATED"
                logger.info(
                    f"[ST-BUILDER] Flip: {old_line.direction.name} -> {current_dir.name} | "
                    f"Old line {status} (pts={old_line.point_count})"
                )

            new_line = self._create_line(current_dir, st_point, timestamp)
            self._state.current_line = new_line
            self._state.prev_direction = current_dir
            self._state.flip_count += 1
            self._state.last_flip_ts = timestamp
            self._all_lines.append(new_line)
            self._state.prev_st_point = st_point
            return new_line

        line = self._state.current_line
        if line:
            line.point_count += 1
            if line.is_pending and line.point_count >= CONFIG.st_line_min_points:
                line.validate()
                logger.info(f"[ST-BUILDER] Line VALIDATED: {line.direction.name} @ {line.price_level}")

        self._state.prev_st_point = st_point
        return None

    def _create_line(self, direction: Direction, price: Decimal, ts: int) -> SupertrendLine:
        line_id = f"STL_{direction.name[:1]}_{ts}_{uuid.uuid4().hex[:6]}"
        return SupertrendLine(
            id=line_id, direction=direction, price_level=price,
            start_ts=ts, point_count=1, status=LineStatus.PENDING
        )

    def reset(self) -> None:
        self._state = BuilderState()
        self._all_lines.clear()
