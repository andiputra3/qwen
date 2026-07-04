"""
Risk Management Engine - Position Sizing + Circuit Breaker.
Validates against actual account balance. Enforces daily DD limits.
Circuit breaker activates when daily loss exceeds max_daily_dd_pct.
"""
from decimal import Decimal
import logging, time

from st_lms_core.config.settings import CONFIG
from st_lms_core.core.models.trade import TradeProposal

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(self):
        self._daily_pnl: Decimal = Decimal("0")
        self._daily_reset_ts: int = 0
        self._circuit_breaker_active: bool = False
        self._open_position_count: int = 0

    def validate_entry(self, proposal: TradeProposal,
                       account_balance: Decimal) -> tuple:
        now = int(time.time())
        day_start = now - (now % 86400)
        if day_start != self._daily_reset_ts:
            self._daily_pnl = Decimal("0")
            self._daily_reset_ts = day_start
            self._circuit_breaker_active = False

        if self._circuit_breaker_active:
            return False, "CIRCUIT_BREAKER: Daily DD limit exceeded"

        if self._open_position_count >= CONFIG.max_open_positions:
            return False, f"MAX_POSITIONS: {self._open_position_count} already open"

        risk_amount = proposal.entry_price * (proposal.risk_pct / Decimal("100"))
        max_risk = account_balance * (CONFIG.max_risk_per_trade_pct / Decimal("100"))
        if risk_amount > max_risk:
            return False, f"RISK_EXCEEDED: {risk_amount:.2f} > {max_risk:.2f}"

        daily_dd_pct = (abs(self._daily_pnl) / account_balance * Decimal("100")) if account_balance > 0 else Decimal("0")
        if daily_dd_pct >= CONFIG.max_daily_dd_pct:
            self._circuit_breaker_active = True
            return False, f"DAILY_DD_LIMIT: {daily_dd_pct:.2f}% >= {CONFIG.max_daily_dd_pct}%"

        return True, "RISK_VALIDATED"

    def record_trade_pnl(self, pnl: Decimal):
        self._daily_pnl += pnl
        logger.info(f"[RISK] Daily PnL updated: {self._daily_pnl:.4f}")

    def on_position_opened(self):
        self._open_position_count += 1

    def on_position_closed(self):
        self._open_position_count = max(0, self._open_position_count - 1)

    @property
    def is_circuit_breaker_active(self) -> bool:
        return self._circuit_breaker_active

    def reset(self):
        self._daily_pnl = Decimal("0")
        self._circuit_breaker_active = False
        self._open_position_count = 0
