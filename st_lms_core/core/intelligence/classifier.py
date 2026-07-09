"""
Classifier - Generates immutable ClassificationTag from ContextSynthesis.
5-Dimension hash key for Dual River pattern matching.
Deterministic: same input always produces same hash.
"""
import logging
from st_lms_core.core.models.context import ContextSynthesis, ClassificationTag

logger = logging.getLogger(__name__)


class Classifier:
    @staticmethod
    def classify(ctx: ContextSynthesis, velocity_regime: str) -> ClassificationTag:
        if ctx.wave_length < 5:
            wave_bucket = "SHORT"
        elif ctx.wave_length <= 12:
            wave_bucket = "NORMAL"
        else:
            wave_bucket = "LONG"

        hash_key = (
            f"{ctx.trend_state}|{ctx.wave_direction or 'NONE'}|"
            f"{wave_bucket}|{ctx.stack_priority}|{ctx.compressed}|"
            f"{ctx.macd_state}|{ctx.oi_state or 'ABSENT'}"
        )

        tag = ClassificationTag(
            hash_key=hash_key, trend_label=ctx.trend_state,
            velocity_regime=velocity_regime, compressed=ctx.compressed,
            macd_bucket=ctx.macd_state, oi_bucket=ctx.oi_state or "ABSENT",
            wave_length_bucket=wave_bucket, stack_priority=ctx.stack_priority
        )
        logger.debug(f"[CLASSIFY] Tag={hash_key[:60]}...")
        return tag
