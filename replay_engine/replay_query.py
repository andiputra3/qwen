"""
Replay Query Engine - POST-AUDIT FIXED VERSION
Fix P2-2: Pagination added to all query methods
"""
from typing import List, Optional, Dict
from replay_engine.models import ReplaySTLine, ReplayWave, ReplayTrade, ReplaySnapshot
from replay_engine.replay_timeline import ReplayTimeline


class ReplayQueryEngine:
    def __init__(self, timeline: ReplayTimeline, lines: List[ReplaySTLine],
                 waves: List[ReplayWave], trades: List[ReplayTrade],
                 snapshots: List[ReplaySnapshot]):
        self.timeline = timeline
        self.lines = lines
        self.waves = waves
        self.trades = trades
        self.snapshots = snapshots

    def query_lines(self, timeframe: Optional[str] = None,
                    direction: Optional[str] = None,
                    status: Optional[str] = None,
                    offset: int = 0, limit: int = 100) -> List[ReplaySTLine]:
        result = self.lines
        if timeframe:
            result = [l for l in result if l.timeframe == timeframe]
        if direction:
            result = [l for l in result if l.direction == direction]
        if status:
            result = [l for l in result if l.status == status]
        return result[offset:offset + limit]

    def query_waves(self, timeframe: Optional[str] = None,
                    direction: Optional[str] = None,
                    offset: int = 0, limit: int = 100) -> List[ReplayWave]:
        result = self.waves
        if timeframe:
            result = [w for w in result if w.timeframe == timeframe]
        if direction:
            result = [w for w in result if w.direction == direction]
        return result[offset:offset + limit]

    def query_trades(self, direction: Optional[str] = None,
                     min_pnl: Optional[float] = None,
                     max_pnl: Optional[float] = None,
                     offset: int = 0, limit: int = 100) -> List[ReplayTrade]:
        result = self.trades
        if direction:
            result = [t for t in result if t.direction == direction]
        if min_pnl is not None:
            result = [t for t in result if t.pnl_pct >= min_pnl]
        if max_pnl is not None:
            result = [t for t in result if t.pnl_pct <= max_pnl]
        return result[offset:offset + limit]

    def query_timeline(self, offset: int = 0, limit: int = 500, **kwargs) -> List[dict]:
        events = self.timeline.get_events(**kwargs)
        return [e.to_dict() for e in events[offset:offset + limit]]

    def get_breakpoint(self, timestamp: int) -> Dict:
        return self.timeline.get_breakpoint(timestamp)

    def get_full_report(self) -> Dict:
        return {
            "timeline_summary": self.timeline.get_summary(),
            "lines_count": len(self.lines),
            "waves_count": len(self.waves),
            "trades_count": len(self.trades),
            "snapshots_count": len(self.snapshots),
            "lines_by_tf": {
                tf: len([l for l in self.lines if l.timeframe == tf])
                for tf in ["4h", "1h", "30m", "15m", "5m", "3m", "1m"]
            },
        }
