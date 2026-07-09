"""
Corrected Exit Monitor - CRASH-FIXED VERSION (P0-2 + Fix #4)
Fix: Guard against empty latest_valid_lines to prevent ZeroDivisionError/AttributeError.
Direction-aware Partial TP using normalized Fib levels.
"""
from decimal import Decimal
from typing import Optional, List
import logging

from st_lms_core.config.settings import CONFIG
from st_lms_core.core.models.trade import ExitSignal
from st_lms_core.core.models.enums import Direction, ExitTrigger
from st_lms_core.core.models.supertrend_line import SupertrendLine
from st_lms_core.core.models.position_state import PositionState
from st_lms_core.core.models.fib_levels import FibLevels

logger = logging.getLogger(__name__)


class ExitMonitor:
    def evaluate(self, pos: PositionState, current_close: Decimal,
                 current_low: Decimal, current_high: Decimal,
                 guard_line: SupertrendLine, current_ts: int,
                 latest_valid_lines: Optional[List[SupertrendLine]] = None) -> Optional[ExitSignal]:
        self._update_trailing_stop(pos, current_close, current_high, current_low, latest_valid_lines)

        if not pos.partial_tp_taken and isinstance(pos.fib_levels, FibLevels):
            partial_signal = self._check_partial_tp(pos, current_close)
            if partial_signal:
                return partial_signal

        trail_signal = self._check_trailing_stop_breach(pos, current_close)
        if trail_signal:
            return trail_signal

        guard_price = guard_line.price_level
        if pos.direction == Direction.BULLISH:
            is_guard_broken = current_close < guard_price
            is_touching_guard = self._is_touch(current_low, current_high, guard_price)
        else:
            is_guard_broken = current_close > guard_price
            is_touching_guard = self._is_touch(current_low, current_high, guard_price)

        if pos.retouched_after_break:
            if is_touching_guard:
                pos.touch_count_after_break += 1
                if pos.touch_count_after_break >= 2:
                    return ExitSignal(pos.position_id, ExitTrigger.EXIT_B_FAKEOUT, current_close,
                                      f"EXIT-B: {pos.touch_count_after_break} retouches after break")

        if is_guard_broken and pos.break_detected_ts is None:
            pos.break_detected_ts = current_ts
        elif pos.break_detected_ts is not None and not is_guard_broken:
            if is_touching_guard:
                pos.retouched_after_break = True
                pos.touch_count_after_break = 1
                pos.break_detected_ts = None
        elif pos.break_detected_ts is not None and is_guard_broken:
            if current_ts > pos.break_detected_ts:
                pos.break_detected_ts = None
                return None

        if not is_guard_broken and is_touching_guard:
            if not pos.single_touch_detected:
                pos.single_touch_detected = True
        elif pos.single_touch_detected and not is_touching_guard and not is_guard_broken:
            pos.retouched_after_single = True
            if isinstance(pos.fib_levels, FibLevels):
                exit_price = (pos.fib_levels.exit_c_long if pos.direction == Direction.BULLISH
                              else pos.fib_levels.exit_c_short)
                return ExitSignal(pos.position_id, ExitTrigger.EXIT_C_REJECTION, exit_price,
                                  "EXIT-C: Single touch rejection on guard line")
        return None

    def _update_trailing_stop(self, pos, close, high, low, latest_valid_lines):
        """Safely handle None or empty latest_valid_lines."""
        if pos.direction == Direction.BULLISH:
            if high > pos.best_price_since_entry:
                pos.best_price_since_entry = high
            if latest_valid_lines:
                bullish = [l for l in latest_valid_lines
                           if l.direction == Direction.BULLISH and l.price_level < close]
                if bullish:
                    new_trail = max(bullish, key=lambda l: l.price_level).price_level
                    if new_trail > pos.trailing_stop_level:
                        pos.trailing_stop_level = new_trail
        else:
            if low < pos.best_price_since_entry:
                pos.best_price_since_entry = low
            if latest_valid_lines:
                bearish = [l for l in latest_valid_lines
                           if l.direction == Direction.BEARISH and l.price_level > close]
                if bearish:
                    new_trail = min(bearish, key=lambda l: l.price_level).price_level
                    if new_trail < pos.trailing_stop_level:
                        pos.trailing_stop_level = new_trail

    def _check_partial_tp(self, pos, close):
        """Direction-aware partial TP using normalized Fib levels."""
        if not isinstance(pos.fib_levels, FibLevels):
            return None
        fib = pos.fib_levels
        if pos.direction == Direction.BULLISH:
            target = fib.level_618
            if close >= target:
                pos.partial_tp_taken = True
                pos.trailing_stop_level = pos.entry_price
                return ExitSignal(pos.position_id, ExitTrigger.EXIT_PARTIAL_TP, target,
                                  f"PARTIAL-TP: Fib 0.618 @ {target} -> SL to breakeven")
        else:
            target = fib.level_382
            if close <= target:
                pos.partial_tp_taken = True
                pos.trailing_stop_level = pos.entry_price
                return ExitSignal(pos.position_id, ExitTrigger.EXIT_PARTIAL_TP, target,
                                  f"PARTIAL-TP: Fib 0.382 @ {target} -> SL to breakeven")
        return None

    def _check_trailing_stop_breach(self, pos, close):
        if pos.direction == Direction.BULLISH and close < pos.trailing_stop_level:
            return ExitSignal(pos.position_id, ExitTrigger.EXIT_TRAILING_STOP, pos.trailing_stop_level,
                              f"TRAILING-STOP: Breached @ {pos.trailing_stop_level}")
        elif pos.direction == Direction.BEARISH and close > pos.trailing_stop_level:
            return ExitSignal(pos.position_id, ExitTrigger.EXIT_TRAILING_STOP, pos.trailing_stop_level,
                              f"TRAILING-STOP: Breached @ {pos.trailing_stop_level}")
        return None

    @staticmethod
    def _is_touch(low, high, level):
        tolerance = level * CONFIG.touch_tolerance_pct
        return (low <= level + tolerance) and (high >= level - tolerance)
