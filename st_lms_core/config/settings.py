"""
ST-LMS Global Configuration - LOCKED FINAL.
Supertrend parameters HARDCODED. No runtime overrides allowed.
Frozen dataclass prevents accidental mutation.
"""
from decimal import Decimal
from dataclasses import dataclass


@dataclass(frozen=True)
class STLMSSettings:
    st_period: int = 10
    st_multiplier: Decimal = Decimal("3")
    st_line_min_points: int = 4
    touch_tolerance_pct: Decimal = Decimal("0.001")
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    max_risk_per_trade_pct: Decimal = Decimal("0.02")
    max_daily_dd_pct: Decimal = Decimal("0.05")
    max_open_positions: int = 1
    river_min_confidence: Decimal = Decimal("0.40")
    river_min_samples: int = 5
    river_save_path: str = "data/dual_river_state.json"
    mode2_min_records: int = 50
    mode3_min_records: int = 200
    position_state_path: str = "data/active_position_state.json"


CONFIG = STLMSSettings()
