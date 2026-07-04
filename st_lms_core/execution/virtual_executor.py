"""
Virtual Executor - CRASH-FIXED VERSION (P0-4 + Fix #2)
Fix: All division operations guarded against zero denominators.
Dynamic position sizing with comprehensive safety checks.
"""
from decimal import Decimal, InvalidOperation
from typing import Optional, List
from dataclasses import dataclass
import time, logging

from st_lms_core.core.models.trade import TradeProposal, AuthorizationResult, ExitSignal
from st_lms_core.core.models.enums import Direction

logger = logging.getLogger(__name__)


@dataclass
class VirtualTrade:
    entry_ts: int
    entry_price: Decimal
    direction: Direction
    stop_loss: Decimal
    leverage: int
    quantity: Decimal
    position_size_usd: Decimal
    classification_tag_hash: str
    exit_ts: Optional[int] = None
    exit_price: Optional[Decimal] = None
    exit_trigger: Optional[str] = None
    pnl_pct: Optional[Decimal] = None
    pnl_usd: Optional[Decimal] = None
    fee_usd: Optional[Decimal] = None
    duration_candles: Optional[int] = None
    status: str = "OPEN"


class VirtualExecutor:
    FEE_RATE = Decimal("0.0004")

    def __init__(self):
        self._open_trade: Optional[VirtualTrade] = None
        self._trade_history: List[VirtualTrade] = []

    @property
    def open_trade(self) -> Optional[VirtualTrade]:
        return self._open_trade

    @property
    def trade_history(self) -> List[VirtualTrade]:
        return list(self._trade_history)

    def execute_entry(self, proposal: TradeProposal, auth_result: AuthorizationResult,
                      leverage: int = 10, account_balance: Decimal = Decimal("10000")) -> bool:
        if not auth_result.authorized:
            logger.error(f"[VIRTUAL] BLOCKED: No authorization. ID={proposal.id[:8]}")
            return False
        if self._open_trade is not None:
            logger.warning("[VIRTUAL] BLOCKED: Already have open virtual position")
            return False

        try:
            risk_amount = account_balance * (proposal.risk_pct / Decimal("100"))
            stop_distance = abs(proposal.entry_price - proposal.stop_loss)

            if stop_distance <= Decimal("0"):
                logger.error("[VIRTUAL] BLOCKED: Zero or negative stop distance")
                return False

            if proposal.entry_price <= Decimal("0"):
                logger.error("[VIRTUAL] BLOCKED: Zero or negative entry price")
                return False

            stop_distance_pct = stop_distance / proposal.entry_price
            if stop_distance_pct <= Decimal("0"):
                logger.error("[VIRTUAL] BLOCKED: Zero stop distance percentage")
                return False

            position_size_usd = risk_amount / stop_distance_pct
            quantity = position_size_usd / proposal.entry_price

            if quantity <= Decimal("0"):
                logger.error("[VIRTUAL] BLOCKED: Calculated quantity is zero")
                return False

        except (InvalidOperation, ZeroDivisionError) as e:
            logger.error(f"[VIRTUAL] BLOCKED: Arithmetic error in sizing: {e}")
            return False

        self._open_trade = VirtualTrade(
            entry_ts=int(time.time() * 1000),
            entry_price=proposal.entry_price,
            direction=proposal.direction,
            stop_loss=proposal.stop_loss,
            leverage=leverage,
            quantity=quantity.quantize(Decimal("0.0001")),
            position_size_usd=position_size_usd.quantize(Decimal("0.01")),
            classification_tag_hash=proposal.classification_tag_hash
        )
        logger.info(
            f"[VIRTUAL] ENTRY | {proposal.direction.name} @ {proposal.entry_price} | "
            f"Qty={quantity:.4f} Size=${position_size_usd:.2f} Lev={leverage}x"
        )
        return True

    def execute_exit(self, signal: ExitSignal) -> bool:
        if self._open_trade is None:
            logger.warning("[VIRTUAL] No open virtual position to close")
            return False

        t = self._open_trade
        entry = t.entry_price
        exit_px = signal.exit_price

        try:
            if t.direction == Direction.BULLISH:
                gross_pnl_usd = (exit_px - entry) * t.quantity
            else:
                gross_pnl_usd = (entry - exit_px) * t.quantity

            if t.position_size_usd > Decimal("0"):
                gross_pnl_pct = (gross_pnl_usd / t.position_size_usd) * Decimal("100")
            else:
                gross_pnl_pct = Decimal("0")

            fee = (t.position_size_usd * self.FEE_RATE) + (abs(exit_px * t.quantity) * self.FEE_RATE)
            net_pnl_usd = gross_pnl_usd - fee

            if t.position_size_usd > Decimal("0"):
                net_pnl_pct = (net_pnl_usd / t.position_size_usd) * Decimal("100")
            else:
                net_pnl_pct = Decimal("0")

        except (InvalidOperation, ZeroDivisionError) as e:
            logger.error(f"[VIRTUAL] PnL calc error: {e}. Recording with zero PnL.")
            gross_pnl_pct = Decimal("0")
            net_pnl_usd = Decimal("0")
            net_pnl_pct = Decimal("0")
            fee = Decimal("0")

        duration = max(1, (int(time.time() * 1000) - t.entry_ts) // 300000)

        t.exit_ts = int(time.time() * 1000)
        t.exit_price = exit_px
        t.exit_trigger = signal.trigger.value
        t.pnl_pct = net_pnl_pct.quantize(Decimal("0.01"))
        t.pnl_usd = net_pnl_usd.quantize(Decimal("0.01"))
        t.fee_usd = fee.quantize(Decimal("0.01"))
        t.duration_candles = duration
        t.status = "CLOSED"

        self._trade_history.append(t)
        closed = t
        self._open_trade = None

        logger.info(
            f"[VIRTUAL] EXIT | {signal.trigger.value} @ {exit_px} | "
            f"PnL={closed.pnl_pct}% (${closed.pnl_usd}) | Fee=${closed.fee_usd} | Dur={duration}c"
        )
        return True
