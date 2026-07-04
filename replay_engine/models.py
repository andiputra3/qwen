"""
Replay Object Models & Lifecycle Enums.
Pure data structures. No trading logic. No formula.
"""
from enum import Enum
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

MISSING_DATA = "__MISSING__"


def safe_get(data: dict, key: str, default=MISSING_DATA):
    """Get value or explicit MISSING marker. Never silently defaults to 0/empty."""
    val = data.get(key)
    if val is None:
        return default
    return val


# ─── LIFECYCLE ENUMS ───────────────────────────────────────

class MeasurementLifecycle(Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    CLOSED = "CLOSED"

class STPointLifecycle(Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    INVALIDATED = "INVALIDATED"

class STLineLifecycle(Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    EXTENDED = "EXTENDED"
    COMPRESSED = "COMPRESSED"
    EXPANDED = "EXPANDED"
    BROKEN = "BROKEN"
    MERGED = "MERGED"
    CLOSED = "CLOSED"

class WaveLifecycle(Enum):
    CREATED = "CREATED"
    BUILDING = "BUILDING"
    ACTIVE = "ACTIVE"
    EXPANDING = "EXPANDING"
    WEAKENING = "WEAKENING"
    CLOSED = "CLOSED"

class StackLifecycle(Enum):
    CREATED = "CREATED"
    BUILDING = "BUILDING"
    READY = "READY"
    ACTIVE = "ACTIVE"
    COLLAPSING = "COLLAPSING"
    CLOSED = "CLOSED"

class TrendLifecycle(Enum):
    UNKNOWN = "UNKNOWN"
    SIDEWAY = "SIDEWAY"
    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    WEAKENING = "WEAKENING"
    REVERSING = "REVERSING"


# ─── REPLAY OBJECTS ────────────────────────────────────────

@dataclass
class ReplayEvent:
    """Single atomic event in the replay timeline."""
    timestamp: int
    event_type: str           # e.g., "ST_LINE_CREATED", "TRADE_OPENED"
    object_type: str          # e.g., "SupertrendLine", "Wave", "Trade"
    object_id: str
    lifecycle: str            # Lifecycle enum value
    timeframe: str
    data: Dict[str, Any] = field(default_factory=dict)
    linked_objects: Dict[str, str] = field(default_factory=dict)  # {type: id}

    def to_dict(self) -> dict:
        return {
            "ts": self.timestamp,
            "event": self.event_type,
            "object": self.object_type,
            "id": self.object_id,
            "lifecycle": self.lifecycle,
            "tf": self.timeframe,
            "data": self.data,
            "links": self.linked_objects,
        }


@dataclass
class ReplaySTLine:
    """Reconstructed Supertrend Line with full lifecycle."""
    id: str
    timeframe: str
    direction: str
    price: float
    created_ts: int
    closed_ts: Optional[int] = None
    lifecycle_history: List[ReplayEvent] = field(default_factory=list)
    start_point: Optional[float] = None
    end_point: Optional[float] = None
    length_points: int = 0
    duration_candles: int = 0
    strength: float = 0.0
    compression_reason: Optional[str] = None
    status: str = "ACTIVE"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "tf": self.timeframe, "direction": self.direction,
            "price": self.price, "created_ts": self.created_ts,
            "closed_ts": self.closed_ts, "status": self.status,
            "start_point": self.start_point, "end_point": self.end_point,
            "length_points": self.length_points, "duration_candles": self.duration_candles,
            "strength": self.strength, "compression_reason": self.compression_reason,
            "lifecycle_events": len(self.lifecycle_history),
        }


@dataclass
class ReplayWave:
    """Reconstructed Wave with full lifecycle."""
    id: str
    timeframe: str
    direction: str
    start_line_id: str
    created_ts: int
    end_line_id: Optional[str] = None
    closed_ts: Optional[int] = None
    start_price: float = 0.0
    end_price: float = 0.0
    amplitude: float = 0.0
    length_points: int = 0
    duration_candles: int = 0
    wave_strength: float = 0.0
    lifecycle_history: List[ReplayEvent] = field(default_factory=list)
    status: str = "BUILDING"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "tf": self.timeframe, "direction": self.direction,
            "start_line": self.start_line_id, "end_line": self.end_line_id,
            "created_ts": self.created_ts, "closed_ts": self.closed_ts,
            "start_price": self.start_price, "end_price": self.end_price,
            "amplitude": self.amplitude, "length_points": self.length_points,
            "duration_candles": self.duration_candles,
            "wave_strength": self.wave_strength, "status": self.status,
            "lifecycle_events": len(self.lifecycle_history),
        }


@dataclass
class ReplayTrade:
    """Reconstructed Trade with full decision context."""
    trade_id: str
    direction: str
    entry_ts: int
    exit_ts: Optional[int] = None
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    pnl_pct: float = 0.0
    pnl_usd: float = 0.0
    reason_entry: str = ""
    reason_exit: Optional[str] = None
    guard_line_id: Optional[str] = None
    trend_at_entry: str = ""
    trend_at_exit: Optional[str] = None
    wave_at_entry: Optional[str] = None
    stack_at_entry: Optional[str] = None
    proposal_id: Optional[str] = None
    confluence_score: float = 0.0
    auth_layers_passed: int = 0
    lifecycle_history: List[ReplayEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id, "direction": self.direction,
            "entry_ts": self.entry_ts, "exit_ts": self.exit_ts,
            "entry_price": self.entry_price, "exit_price": self.exit_price,
            "pnl_pct": self.pnl_pct, "pnl_usd": self.pnl_usd,
            "reason_entry": self.reason_entry, "reason_exit": self.reason_exit,
            "guard_line": self.guard_line_id,
            "trend_entry": self.trend_at_entry, "trend_exit": self.trend_at_exit,
            "wave_entry": self.wave_at_entry, "stack_entry": self.stack_at_entry,
            "proposal": self.proposal_id, "confluence": self.confluence_score,
            "auth_passed": self.auth_layers_passed,
            "lifecycle_events": len(self.lifecycle_history),
        }


@dataclass
class ReplaySnapshot:
    """Complete bot state at a point in time."""
    timestamp: int
    timeframe: str
    price: float
    trend_state: str
    structural_form: str
    macd_bucket: str
    oi_state: str
    stack_priority: str
    compressed: bool
    active_lines_count: int
    valid_lines_count: int
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None
    fib_levels: Optional[Dict] = None
    last_wave_id: Optional[str] = None
    confluence_score: Optional[float] = None
    decision: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "ts": self.timestamp, "tf": self.timeframe, "price": self.price,
            "trend": self.trend_state, "form": self.structural_form,
            "macd": self.macd_bucket, "oi": self.oi_state,
            "priority": self.stack_priority, "compressed": self.compressed,
            "active_lines": self.active_lines_count,
            "valid_lines": self.valid_lines_count,
            "support": self.nearest_support, "resistance": self.nearest_resistance,
            "fib": self.fib_levels, "last_wave": self.last_wave_id,
            "confluence": self.confluence_score, "decision": self.decision,
        }


@dataclass
class ReplayAuditResult:
    """Result of replay integrity audit."""
    total_events: int = 0
    total_snapshots: int = 0
    total_lines: int = 0
    total_waves: int = 0
    total_trades: int = 0
    missing_snapshots: List[str] = field(default_factory=list)
    missing_events: List[str] = field(default_factory=list)
    broken_timelines: List[str] = field(default_factory=list)
    orphan_objects: List[str] = field(default_factory=list)
    broken_links: List[str] = field(default_factory=list)
    consistency_score: float = 0.0
    certification: str = "FAIL"
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_events": self.total_events,
            "total_snapshots": self.total_snapshots,
            "total_lines": self.total_lines,
            "total_waves": self.total_waves,
            "total_trades": self.total_trades,
            "missing_snapshots": len(self.missing_snapshots),
            "missing_events": len(self.missing_events),
            "broken_timelines": len(self.broken_timelines),
            "orphan_objects": len(self.orphan_objects),
            "broken_links": len(self.broken_links),
            "consistency_score": round(self.consistency_score, 4),
            "certification": self.certification,
            "issues": self.issues,
        }
