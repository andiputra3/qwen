"""
Trade Models - Proposal, Authorization, Exit Signal.
Core data structures for Governance and Execution layers.
"""
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from st_lms_core.core.models.enums import Direction, ExitTrigger


@dataclass
class TradeProposal:
    id: str
    direction: Direction
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Optional[Decimal]
    risk_pct: Decimal
    support_line_id: str
    wave_id: Optional[str]
    classification_tag_hash: str


@dataclass
class AuthorizationResult:
    proposal_id: str
    authorized: bool
    reason: str
    mode_at_decision: str
    confidence_score: float


@dataclass
class ExitSignal:
    position_id: str
    trigger: ExitTrigger
    exit_price: Decimal
    reason: str
