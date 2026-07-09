"""
Replay Storage - POST-AUDIT FIXED VERSION
Fix P1-4: River patterns as ReplayEvents
Fix P2-1: Cache invalidation via mtime check
"""
import json
import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class ReplayStorage:
    def __init__(self, data_dir: str = "data/multi_tf_state"):
        self.data_dir = Path(data_dir)
        self.tf_dir = self.data_dir / "timeframes"
        self.lines_dir = self.data_dir / "st_lines"
        self.global_file = self.data_dir / "global_state.json"
        self.trades_file = Path("data/performance/trades.csv")
        self.metrics_file = Path("data/performance/metrics.json")
        self.river_file = Path("data/multi_tf_river.json")

        self._snapshot_cache: Dict[str, Dict] = {}
        self._line_index: List[Dict] = []
        self._trade_index: List[Dict] = []
        self._index_built = False
        self._file_mtimes: Dict[str, float] = {}

        self._executor = ThreadPoolExecutor(max_workers=4)

    def _check_cache_stale(self, filepath: Path) -> bool:
        if not filepath.exists():
            return True
        mtime = filepath.stat().st_mtime
        cached_mtime = self._file_mtimes.get(str(filepath), 0)
        if mtime > cached_mtime:
            self._file_mtimes[str(filepath)] = mtime
            return True
        return False

    def build_index(self):
        logger.info("[REPLAY-STORAGE] Building index...")

        if self.tf_dir.exists():
            for f in sorted(self.tf_dir.glob("*.json")):
                try:
                    with open(f) as fh:
                        data = json.load(fh)
                    tf = f.stem
                    self._snapshot_cache[tf] = data
                except Exception as e:
                    logger.warning(f"[REPLAY-STORAGE] Failed to read {f}: {e}")

        lines_file = self.lines_dir / "all_st_lines.json"
        if lines_file.exists():
            try:
                with open(lines_file) as f:
                    data = json.load(f)
                self._line_index = data.get("lines", [])
            except Exception as e:
                logger.warning(f"[REPLAY-STORAGE] Failed to read lines: {e}")

        if self.trades_file.exists():
            try:
                with open(self.trades_file) as f:
                    reader = csv.DictReader(f)
                    self._trade_index = list(reader)
            except Exception as e:
                logger.warning(f"[REPLAY-STORAGE] Failed to read trades: {e}")

        self._index_built = True
        logger.info(
            f"[REPLAY-STORAGE] Index built: "
            f"{len(self._snapshot_cache)} TF snapshots, "
            f"{len(self._line_index)} lines, "
            f"{len(self._trade_index)} trades"
        )

    def reload_if_stale(self):
        stale = False
        for path in [self.global_file, self.lines_dir / "all_st_lines.json", self.trades_file]:
            if self._check_cache_stale(path):
                stale = True
                break
        if stale:
            logger.info("[REPLAY-STORAGE] Stale cache detected, rebuilding index...")
            self.build_index()

    def get_tf_snapshot(self, timeframe: str) -> Optional[Dict]:
        return self._snapshot_cache.get(timeframe)

    def get_all_snapshots(self) -> Dict[str, Dict]:
        return dict(self._snapshot_cache)

    def get_all_lines(self) -> List[Dict]:
        return list(self._line_index)

    def get_lines_by_tf(self, timeframe: str) -> List[Dict]:
        return [l for l in self._line_index if l.get("timeframe") == timeframe]

    def get_active_lines(self) -> List[Dict]:
        return [l for l in self._line_index if l.get("is_active")]

    def get_all_trades(self) -> List[Dict]:
        return list(self._trade_index)

    def get_global_state(self) -> Optional[Dict]:
        if self.global_file.exists():
            try:
                with open(self.global_file) as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def get_metrics(self) -> Optional[Dict]:
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file) as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def get_river_patterns(self) -> Optional[Dict]:
        if self.river_file.exists():
            try:
                with open(self.river_file) as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def get_river_events(self) -> List[dict]:
        events = []
        river_data = self.get_river_patterns()
        if not river_data:
            return events
        for pattern_key, pattern in river_data.items():
            events.append({
                "ts": pattern.get("last_updated_ts", 0),
                "event": "RIVER_PATTERN_UPDATED",
                "object": "RiverPattern",
                "id": pattern_key[:50],
                "tf": "MULTI_TF",
                "data": {
                    "win_rate": pattern.get("win_rate", 0),
                    "total_trades": pattern.get("total_trades", 0),
                    "confidence": pattern.get("confidence", 0),
                }
            })
        return events

    def load_snapshot_history(self, timeframe: str) -> List[Dict]:
        history = []
        tf_history_dir = self.data_dir / "history" / timeframe
        if tf_history_dir.exists():
            for f in sorted(tf_history_dir.glob("*.json")):
                try:
                    with open(f) as fh:
                        history.append(json.load(fh))
                except Exception:
                    continue
        return history

    def shutdown(self):
        self._executor.shutdown(wait=False)
