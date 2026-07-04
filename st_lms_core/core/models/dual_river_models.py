"""
Dual River Models. EntryPattern and ExitPattern with 5-dimension encoding.
Includes separate OI ON/OFF win rate tracking with graceful degradation.
"""
from decimal import Decimal
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class EntryPattern:
    hash_key: str
    st_direction: str
    wave_direction: str
    wave_length_bucket: str
    stack_priority: str
    compressed: bool
    macd_bucket: str
    oi_state: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: Decimal = Decimal("0")
    avg_hold_candles: float = 0.0
    last_updated_ts: int = 0
    oi_on_trades: int = 0
    oi_on_wins: int = 0
    oi_off_trades: int = 0
    oi_off_wins: int = 0

    @property
    def win_rate(self) -> float:
        return self.wins / self.total_trades if self.total_trades > 0 else 0.0

    @property
    def oi_on_win_rate(self) -> float:
        return self.oi_on_wins / self.oi_on_trades if self.oi_on_trades > 0 else 0.0

    @property
    def oi_off_win_rate(self) -> float:
        return self.oi_off_wins / self.oi_off_trades if self.oi_off_trades > 0 else 0.0

    @property
    def profit_factor(self) -> float:
        if self.total_trades == 0:
            return 0.0
        avg_win = (self.total_pnl / self.wins) if self.wins > 0 else Decimal("0")
        avg_loss = abs(self.total_pnl / self.losses) if self.losses > 0 else Decimal("0")
        if avg_loss == 0:
            return float('inf') if avg_win > 0 else 0.0
        return float(avg_win / avg_loss)

    @property
    def confidence_score(self) -> float:
        if self.total_trades < 5:
            return 0.0
        wr = self.win_rate * 0.5
        pf = min(self.profit_factor, 5.0) / 5.0 * 0.3
        sample = min(self.total_trades / 30, 1.0) * 0.2
        return min(wr + pf + sample, 1.0)


@dataclass
class ExitPattern:
    hash_key: str
    entry_pattern_hash: str
    exit_trigger: str
    hold_candles_bucket: str
    pnl_bucket: str
    macd_at_exit: str
    oi_at_exit: str
    st_break_status: str
    total_exits: int = 0
    exits_at_peak: int = 0
    exits_before_reversal: int = 0
    exits_too_early: int = 0
    exits_too_late: int = 0
    avg_pnl: Decimal = Decimal("0")
    optimal_hold_range: Optional[Tuple[int, int]] = None
