"""
ST-LMS Pipeline Orchestrator - FINAL AUDITED VERSION
Processes candles through Measure -> Structure -> Intelligence layers.
Stores _last_st_point, _last_velocity, _last_proposal for external tap.
Passes ATR to AdaptiveStack (Fix #4 integration).
Locked Config: No parameter overrides allowed.
"""
from decimal import Decimal
from typing import Optional
import logging

from st_lms_core.config.settings import CONFIG
from st_lms_core.core.models.candle import Candle
from st_lms_core.core.calculators.supertrend_calculator import SupertrendCalculator
from st_lms_core.core.calculators.macd_calculator import MACDCalculator
from st_lms_core.core.calculators.fibonacci_calculator import FibonacciCalculator
from st_lms_core.core.calculators.oi_analyzer import OIAnalyzer
from st_lms_core.core.calculators.volatility_calculator import VolatilityCalculator
from st_lms_core.core.structure.st_line_builder import STLineBuilder
from st_lms_core.core.structure.wave_builder import WaveBuilder
from st_lms_core.core.structure.adaptive_stack import AdaptiveStack
from st_lms_core.core.structure.trend_geometry import TrendGeometry
from st_lms_core.core.structure.trend_classifier import TrendClassifier
from st_lms_core.core.intelligence.context_synthesizer import ContextSynthesizer
from st_lms_core.core.intelligence.classifier import Classifier

logger = logging.getLogger(__name__)


class STLMSPipeline:
    def __init__(self):
        self._st_calc = SupertrendCalculator()
        self._macd_calc = MACDCalculator()
        self._fib_calc = FibonacciCalculator()
        self._oi_analyzer = OIAnalyzer()
        self._vol_calc = VolatilityCalculator()
        self._line_builder = STLineBuilder()
        self._wave_builder = WaveBuilder()
        self._stack = AdaptiveStack()
        self._trend_geom = TrendGeometry()
        self._trend_cls = TrendClassifier()
        self._context_synth = ContextSynthesizer()
        self._classifier = Classifier()
        self._prev_line = None
        self._candle_count = 0

        self._last_st_point: Optional[Decimal] = None
        self._last_velocity: str = "NORMAL_FLOW"
        self._last_proposal = None

    @property
    def is_warmup_complete(self) -> bool:
        return self._st_calc.is_warmup_complete

    def process_candle(self, candle: Candle, macd_state: str = "NEUTRAL",
                       oi_state: Optional[str] = None) -> Optional[dict]:
        self._candle_count += 1
        self._last_proposal = None

        # === MEASURE LAYER ===
        st_point = self._st_calc.calculate(candle.high, candle.low, candle.close)
        if st_point is None:
            return None

        candle.st_point = st_point
        self._last_st_point = st_point

        macd_bucket = self._macd_calc.calculate(candle.close)
        atr = self._vol_calc.update(candle.high, candle.low, candle.close)
        velocity = "NORMAL_FLOW"
        oi_state_resolved = oi_state or self._oi_analyzer.classify(candle.oi_value)

        # === STRUCTURE LAYER ===
        new_line = self._line_builder.process_st_point(st_point, candle.close, candle.timestamp)
        completed_wave = None
        if new_line is not None:
            completed_wave = self._wave_builder.on_new_line(new_line, self._prev_line)
            self._prev_line = new_line

        active_context = self._stack.select_living_structures(
            self._line_builder.all_lines, self._wave_builder.all_waves,
            candle.close, candle.timestamp,
            current_atr=atr
        )

        last_wave = self._wave_builder.last_completed_wave
        structural_form = self._trend_geom.analyze(active_context)
        market_state = self._trend_cls.classify(structural_form)

        if last_wave:
            velocity = self._vol_calc.classify_velocity(last_wave.length_points, last_wave.amplitude)

        self._last_velocity = velocity

        # === INTELLIGENCE LAYER ===
        context = self._context_synth.synthesize(
            timestamp=candle.timestamp, price=candle.close,
            market_state=market_state, structural_form=structural_form,
            last_wave=last_wave, active_context=active_context,
            macd_bucket=macd_bucket, oi_state=oi_state_resolved,
            velocity_regime=velocity
        )
        tag = self._classifier.classify(context, velocity)
        fib_levels = self._fib_calc.compute(last_wave)

        self._last_context = context
        self._last_tag = tag
        self._last_active_context = active_context
        self._last_fib = fib_levels
        self._last_macd = macd_bucket
        self._last_oi = oi_state_resolved

        return {
            "ts": candle.timestamp, "price": float(candle.close),
            "st_point": float(st_point), "macd": macd_bucket,
            "oi": oi_state_resolved, "trend": market_state.value,
            "form": structural_form.value, "velocity": velocity,
            "compressed": context.compressed, "stack_priority": context.stack_priority,
            "wave_direction": last_wave.direction.value if last_wave else None,
            "wave_length": last_wave.length_points if last_wave else 0,
            "classification": tag.hash_key, "fib_available": fib_levels is not None
        }

    def reset(self) -> None:
        self._st_calc.reset()
        self._macd_calc.reset()
        self._oi_analyzer.reset()
        self._vol_calc.reset()
        self._line_builder.reset()
        self._wave_builder.reset()
        self._prev_line = None
        self._candle_count = 0
        self._last_st_point = None
        self._last_velocity = "NORMAL_FLOW"
        self._last_proposal = None
