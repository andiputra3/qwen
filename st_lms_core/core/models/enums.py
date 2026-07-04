"""
ST-LMS Core Enumerations - FINAL CONSTITUTIONAL
Includes MarketState, StructuralForm, Dual River v2.0, Enhanced Exits.
"""
from enum import Enum


class Direction(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class LineStatus(Enum):
    PENDING = "PENDING"
    VALID = "VALID"
    DEACTIVATED = "DEACTIVATED"
    NEVER_VALID = "NEVER_VALID"


class MarketState(Enum):
    """Official Market State Classifier (C008). UPTREND/DOWNTREND/SIDEWAY only."""
    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    SIDEWAY = "SIDEWAY"


class StructuralForm(Enum):
    """Geometric form of active structure. Output of TrendGeometry."""
    ASCENDING_STAIRS = "ASCENDING_STAIRS"
    DESCENDING_STAIRS = "DESCENDING_STAIRS"
    CONVERGING = "CONVERGING"
    FLAT_CORRIDOR = "FLAT_CORRIDOR"
    SINGLE_DIRECTION = "SINGLE_DIRECTION"
    CHAOTIC = "CHAOTIC"
    NO_STRUCTURE = "NO_STRUCTURE"


class VelocityRegime(Enum):
    SLOW_DRIFT = "SLOW_DRIFT"
    NORMAL_FLOW = "NORMAL_FLOW"
    FAST_IMPULSE = "FAST_IMPULSE"


class MACDBucket(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    WEAKENING = "WEAKENING"
    NEUTRAL = "NEUTRAL"


class OIState(Enum):
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    FLAT = "FLAT"
    ABSENT = "ABSENT"


class ExitTrigger(Enum):
    EXIT_A_HOLD = "EXIT_A_HOLD"
    EXIT_B_FAKEOUT = "EXIT_B_FAKEOUT"
    EXIT_C_REJECTION = "EXIT_C_REJECTION"
    EXIT_PARTIAL_TP = "EXIT_PARTIAL_TP"
    EXIT_TRAILING_STOP = "EXIT_TRAILING_STOP"


class RiverMode(Enum):
    MODE1_COLD_START = "MODE1_COLD_START"
    MODE2_FULL_REC = "MODE2_FULL_REC"
    MODE3_ADAPTIVE = "MODE3_ADAPTIVE"
    MODE4_HIBERNATION = "MODE4_HIBERNATION"


class TradeOutcome(Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"
