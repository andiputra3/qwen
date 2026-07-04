"""
Replay Timeline - POST-AUDIT FIXED VERSION
Fix P1-5: Clock sync validation added
"""
import logging
from typing import List, Optional, Dict
from replay_engine.models import ReplayEvent

logger = logging.getLogger(__name__)


class ReplayTimeline:
    def __init__(self):
        self.events: List[ReplayEvent] = []
        self._sorted = False

    def add_event(self, event: ReplayEvent):
        self.events.append(event)
        self._sorted = False

    def add_events(self, events: List[ReplayEvent]):
        self.events.extend(events)
        self._sorted = False

    def sort(self):
        if not self._sorted:
            self.events.sort(key=lambda e: e.timestamp)
            self._sorted = True

    def get_events(
        self,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        timeframe: Optional[str] = None,
        object_type: Optional[str] = None,
        object_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> List[ReplayEvent]:
        self.sort()
        result = self.events

        if start_ts is not None:
            result = [e for e in result if e.timestamp >= start_ts]
        if end_ts is not None:
            result = [e for e in result if e.timestamp <= end_ts]
        if timeframe is not None:
            result = [e for e in result if e.timeframe == timeframe]
        if object_type is not None:
            result = [e for e in result if e.object_type == object_type]
        if object_id is not None:
            result = [e for e in result if e.object_id == object_id]
        if event_type is not None:
            result = [e for e in result if e.event_type == event_type]

        return result

    def get_breakpoint(self, timestamp: int) -> Dict:
        self.sort()
        events_at = [e for e in self.events if e.timestamp <= timestamp]
        return {
            "timestamp": timestamp,
            "events_count": len(events_at),
            "last_event": events_at[-1].to_dict() if events_at else None,
            "events": [e.to_dict() for e in events_at],
        }

    def validate_clock_sync(self) -> Dict:
        self.sort()
        issues = []
        tf_last_ts: Dict[str, int] = {}
        for event in self.events:
            tf = event.timeframe
            if tf in tf_last_ts:
                gap = event.timestamp - tf_last_ts[tf]
                if gap < 0:
                    issues.append(f"CLOCK_DRIFT: {tf} event at {event.timestamp} before previous {tf_last_ts[tf]}")
            tf_last_ts[tf] = event.timestamp
        return {"sync_issues": len(issues), "details": issues[:20]}

    def get_summary(self) -> Dict:
        self.sort()
        if not self.events:
            return {"total_events": 0}
        return {
            "total_events": len(self.events),
            "first_ts": self.events[0].timestamp,
            "last_ts": self.events[-1].timestamp,
            "event_types": list(set(e.event_type for e in self.events)),
            "object_types": list(set(e.object_type for e in self.events)),
            "timeframes": list(set(e.timeframe for e in self.events)),
        }

    def to_list(self) -> List[dict]:
        self.sort()
        return [e.to_dict() for e in self.events]
