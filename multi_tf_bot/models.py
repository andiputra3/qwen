"""
Multi-TF Data Models - PHASE 3 COMPLETE
Stores complete analysis state per timeframe for confluence engine.
Includes: TFAnalysisSnapshot, ConfluenceResult, TradeDecision, MultiTFPattern
"""
from decimal import Decimal
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class STLineRecord:
    """Immutable record of a single Supertrend Line."""
    id: str
    price: float
    direction: str
    status: str
    point_count: int
    start_ts: int
    end_ts: Optional[int]
    timeframe: str

    @property
    def is_active(self) -> bool:
        return self.status in ("PENDING", "VALID")

    @property
    def is_valid(self) -> bool:
        return self.status == "VALID"


@dataclass
class WaveRecord:
    """Record of a completed Wave."""
    id: str
    direction: str
    start_price: float
    end_price: float
    amplitude: float
    length_points: int
    start_ts: int
    end_ts: int
    timeframe: str


@dataclass
class TFAnalysisSnapshot:
    """
    Complete analysis state for ONE timeframe at a point in time.
    This is what each STLMSPipeline instance produces.
    """
    timeframe: str
    timestamp: int
    price: float
    st_point: Optional[float] = None
    st_lines: List[STLineRecord] = field(default_factory=list)
    last_wave: Optional[WaveRecord] = None
    fib_levels: Optional[Dict[str, float]] = None
    macd_bucket: str = "NEUTRAL"
    oi_state: str = "ABSENT"
    velocity: str = "NORMAL_FLOW"
    trend_state: str = "SIDEWAY"
    structural_form: str = "NO_STRUCTURE"
    stack_priority: str = "LOW"
    compressed: bool = False
    wave_direction: Optional[str] = None
    wave_length: int = 0
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None
    candle_count: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "tf": self.timeframe,
            "ts": self.timestamp,
            "price": self.price,
            "st_point": self.st_point,
            "trend": self.trend_state,
            "form": self.structural_form,
            "macd": self.macd_bucket,
            "oi": self.oi_state,
            "priority": self.stack_priority,
            "compressed": self.compressed,
            "wave_dir": self.wave_direction,
            "wave_len": self.wave_length,
            "support": self.nearest_support,
            "resistance": self.nearest_resistance,
            "active_lines": len([l for l in self.st_lines if l.is_active]),
            "valid_lines": len([l for l in self.st_lines if l.status == "VALID"]),
        }


@dataclass
class ConfluenceZone:
    """Price zone where multiple TF ST lines converge."""
    price_center: float
    price_low: float
    price_high: float
    direction: str
    tf_count: int
    timeframes: List[str]
    line_ids: List[str]
    strength: float


@dataclass
class ConfluenceResult:
    """Result of cross-TF alignment analysis."""
    timestamp: int
    price: float
    confluence_score: float
    dominant_direction: str
    tf_alignment: Dict[str, str]
    zones: List[ConfluenceZone]
    conflict_detected: bool
    reasoning: str
    tf_count_aligned: int
    total_tf_evaluated: int

    def to_dict(self) -> dict:
        return {
            "ts": self.timestamp,
            "price": self.price,
            "score": round(self.confluence_score, 4),
            "direction": self.dominant_direction,
            "alignment": self.tf_alignment,
            "zones": len(self.zones),
            "conflict": self.conflict_detected,
            "aligned": self.tf_count_aligned,
            "total": self.total_tf_evaluated,
            "reasoning": self.reasoning,
        }


@dataclass
class TradeDecision:
    """Single unified trade decision from multi-TF consensus."""
    timestamp: int
    should_trade: bool
    direction: str
    confidence: float
    entry_zone_low: Optional[float] = None
    entry_zone_high: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size_pct: float = 0.0
    confluence: Optional[ConfluenceResult] = None
    river_confidence: float = 0.0
    river_should_enter: bool = False
    reasoning: str = ""
    rejection_reason: Optional[str] = None
    guard_line_id: Optional[str] = None
    guard_line_tf: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "ts": self.timestamp,
            "trade": self.should_trade,
            "direction": self.direction,
            "confidence": round(self.confidence, 4),
            "entry_low": self.entry_zone_low,
            "entry_high": self.entry_zone_high,
            "sl": self.stop_loss,
            "tp": self.take_profit,
            "size_pct": round(self.position_size_pct, 2),
            "guard_id": self.guard_line_id,
            "guard_tf": self.guard_line_tf,
            "confluence_score": self.confluence.confluence_score if self.confluence else 0,
            "river_conf": round(self.river_confidence, 4),
            "reasoning": self.reasoning,
            "rejection": self.rejection_reason,
        }


@dataclass
class MultiTFPattern:
    """Pattern learned from multi-TF alignment + trade outcome."""
    hash_key: str
    alignment_signature: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    avg_confluence_score: float = 0.0
    last_updated_ts: int = 0

    @property
    def win_rate(self) -> float:
        return self.wins / self.total_trades if self.total_trades > 0 else 0.0

    @property
    def confidence(self) -> float:
        if self.total_trades < 5:
            return 0.0
        wr = self.win_rate * 0.5
        sample = min(self.total_trades / 30, 1.0) * 0.3
        pnl_factor = min(max(self.total_pnl / max(self.total_trades, 1), -1.0), 1.0) * 0.2
        return min(max(wr + sample + pnl_factor, 0.0), 1.0)


@dataclass
class MultiTFState:
    """Aggregated state across all timeframes."""
    snapshots: Dict[str, TFAnalysisSnapshot] = field(default_factory=dict)
    last_confluence_ts: int = 0
    last_decision: Optional[TradeDecision] = None
    total_candles_processed: int = 0

    def get_tf(self, tf: str) -> Optional[TFAnalysisSnapshot]:
        return self.snapshots.get(tf)

    def all_tfs_ready(self, required_tfs: List[str]) -> bool:
        return all(tf in self.snapshots for tf in required_tfs)

    def summary(self) -> dict:
        return {
            "timeframes": list(self.snapshots.keys()),
            "ready_count": len(self.snapshots),
            "total_candles": self.total_candles_processed,
            "trends": {tf: s.trend_state for tf, s in self.snapshots.items()},
            "macd": {tf: s.macd_bucket for tf, s in self.snapshots.items()},
            "last_decision": self.last_decision.to_dict() if self.last_decision else None,
        }
