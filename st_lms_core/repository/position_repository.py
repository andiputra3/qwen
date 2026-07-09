"""
Position Persistence Repository - Survive crashes/restarts.
Save only when state changes (dirty flag pattern from Fix #2).
Conditional save prevents unnecessary disk I/O.
"""
import json, os, logging
from decimal import Decimal
from typing import Optional

from st_lms_core.config.settings import CONFIG
from st_lms_core.core.models.position_state import PositionState
from st_lms_core.core.models.enums import Direction

logger = logging.getLogger(__name__)


class PositionRepository:
    @staticmethod
    def save(position: Optional[PositionState]) -> None:
        try:
            os.makedirs(os.path.dirname(CONFIG.position_state_path) or ".", exist_ok=True)
            if position is None:
                with open(CONFIG.position_state_path, "w") as f:
                    json.dump({"active": False}, f)
                logger.debug("[POSITION-REPO] Position cleared")
                return

            data = {
                "active": True,
                "position_id": position.position_id,
                "direction": position.direction.value,
                "guard_line_id": position.guard_line_id,
                "entry_price": str(position.entry_price),
                "break_detected_ts": position.break_detected_ts,
                "retouched_after_break": position.retouched_after_break,
                "touch_count_after_break": position.touch_count_after_break,
                "single_touch_detected": position.single_touch_detected,
                "retouched_after_single": position.retouched_after_single,
                "partial_tp_taken": position.partial_tp_taken,
                "trailing_stop_level": str(position.trailing_stop_level),
                "best_price_since_entry": str(position.best_price_since_entry),
            }
            with open(CONFIG.position_state_path, "w") as f:
                json.dump(data, f)
            logger.info(f"[POSITION-REPO] Saved: {position.position_id[:8]}")
        except Exception as e:
            logger.error(f"[POSITION-REPO] Save failed: {e}")

    @staticmethod
    def load() -> Optional[PositionState]:
        try:
            if not os.path.exists(CONFIG.position_state_path):
                return None
            with open(CONFIG.position_state_path) as f:
                data = json.load(f)
            if not data.get("active", False):
                return None

            pos = PositionState(
                position_id=data["position_id"],
                direction=Direction(data["direction"]),
                guard_line_id=data["guard_line_id"],
                entry_price=Decimal(data["entry_price"]),
                fib_levels=None,
                break_detected_ts=data.get("break_detected_ts"),
                retouched_after_break=data.get("retouched_after_break", False),
                touch_count_after_break=data.get("touch_count_after_break", 0),
                single_touch_detected=data.get("single_touch_detected", False),
                retouched_after_single=data.get("retouched_after_single", False),
                partial_tp_taken=data.get("partial_tp_taken", False),
                trailing_stop_level=Decimal(data.get("trailing_stop_level", data["entry_price"])),
                best_price_since_entry=Decimal(data.get("best_price_since_entry", data["entry_price"])),
            )
            logger.info(f"[POSITION-REPO] Restored: {pos.position_id[:8]}")
            return pos
        except Exception as e:
            logger.warning(f"[POSITION-REPO] Load failed (starting fresh): {e}")
            return None
