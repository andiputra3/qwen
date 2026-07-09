"""
DEPRECATED: Use TrendGeometry + TrendClassifier instead.
Kept for backward compatibility during migration.
Will be removed after all downstream modules are updated.
"""
import warnings
warnings.warn(
    "TrendInterpreter is DEPRECATED. Use TrendGeometry + TrendClassifier instead.",
    DeprecationWarning, stacklevel=2
)

from st_lms_core.core.models.enums import VelocityRegime


class TrendInterpreter:
    """Legacy trend interpreter. DO NOT USE in new code."""

    def interpret(self, active_set, recent_waves, current_price, velocity_regime):
        if hasattr(active_set, 'is_compressed') and active_set.is_compressed:
            return "STRUCTURAL_SIDEWAY"
        if not recent_waves:
            return "STRUCTURAL_SIDEWAY"
        last_wave = recent_waves[-1]
        bullish_waves = sum(1 for w in recent_waves[-5:] if w.direction.value == "BULLISH")
        bearish_waves = sum(1 for w in recent_waves[-5:] if w.direction.value == "BEARISH")
        if bullish_waves >= 4 and velocity_regime == VelocityRegime.FAST_IMPULSE.value:
            return "STRONG_UPTREND"
        if bearish_waves >= 4 and velocity_regime == VelocityRegime.FAST_IMPULSE.value:
            return "STRONG_DOWNTREND"
        if bullish_waves >= 3:
            return "WEAK_UPTREND"
        if bearish_waves >= 3:
            return "WEAK_DOWNTREND"
        if last_wave.direction.value == "BULLISH":
            return "UP_TRANSITION"
        if last_wave.direction.value == "BEARISH":
            return "DOWN_TRANSITION"
        return "STRUCTURAL_SIDEWAY"

    def reset(self) -> None:
        pass
