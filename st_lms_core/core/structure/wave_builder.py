"""
Wave Builder - Constructs Waves from sequential ST Line flips.
A Wave represents structural movement between two consecutive ST Lines.
Event-based: only emits when wave completes.
"""
from decimal import Decimal
from typing import Optional, List
import uuid
import logging

from st_lms_core.core.models.enums import Direction
from st_lms_core.core.models.wave import Wave
from st_lms_core.core.models.supertrend_line import SupertrendLine

logger = logging.getLogger(__name__)


class WaveBuilder:
    def __init__(self):
        self._waves: List[Wave] = []
        self._last_completed_wave: Optional[Wave] = None

    @property
    def all_waves(self) -> List[Wave]:
        return list(self._waves)

    @property
    def last_completed_wave(self) -> Optional[Wave]:
        return self._last_completed_wave

    def on_new_line(self, new_line: SupertrendLine, prev_line: Optional[SupertrendLine]) -> Optional[Wave]:
        if prev_line is None:
            return None

        wave_dir = Direction.BULLISH if new_line.price_level > prev_line.price_level else Direction.BEARISH
        amplitude = abs(new_line.price_level - prev_line.price_level)

        wave_id = f"WAV_{wave_dir.name[:1]}_{new_line.start_ts}_{uuid.uuid4().hex[:6]}"
        wave = Wave(
            id=wave_id, direction=wave_dir,
            start_line_id=prev_line.id, end_line_id=new_line.id,
            start_price=prev_line.price_level, end_price=new_line.price_level,
            length_points=prev_line.point_count, amplitude=amplitude,
            start_ts=prev_line.start_ts, end_ts=new_line.start_ts
        )

        self._waves.append(wave)
        self._last_completed_wave = wave
        logger.info(
            f"[WAVE-BUILDER] Wave completed: {wave_dir.name} | "
            f"Amp={amplitude:.2f} Len={prev_line.point_count}c"
        )
        return wave

    def reset(self) -> None:
        self._waves.clear()
        self._last_completed_wave = None
