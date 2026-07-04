"""
Market State & Structural Form Enums (Constitutional C008).
Trend is Official Market State Classifier. Not a line, not an indicator.
Sideway is a structural classification result, NOT an ATR threshold.
"""
from enum import Enum


class MarketState(Enum):
    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    SIDEWAY = "SIDEWAY"


class StructuralForm(Enum):
    ASCENDING_STAIRS = "ASCENDING_STAIRS"
    DESCENDING_STAIRS = "DESCENDING_STAIRS"
    CONVERGING = "CONVERGING"
    FLAT_CORRIDOR = "FLAT_CORRIDOR"
    SINGLE_DIRECTION = "SINGLE_DIRECTION"
    CHAOTIC = "CHAOTIC"
    NO_STRUCTURE = "NO_STRUCTURE"
