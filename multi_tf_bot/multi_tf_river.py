"""
Multi-TF River Engine
Learns from multi-TF confluence patterns + trade outcomes.
Pattern key = TF alignment signature (e.g., "4h:BULL|1h:BULL|15m:BEAR|5m:BULL")
"""
import json, os, logging
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MultiTFPattern:
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


class MultiTFRiver:
    """
    Learns which multi-TF alignment patterns are profitable.
    Persists state to JSON.
    """

    def __init__(self, save_path: str = "data/multi_tf_river.json"):
        self._patterns: Dict[str, MultiTFPattern] = {}
        self._save_path = save_path
        self._min_samples = 5
        self._min_confidence = 0.35
        self._load()

    @staticmethod
    def make_signature(tf_alignment: Dict[str, str]) -> str:
        """Create deterministic signature from TF alignment."""
        ordered = ["4h", "1h", "30m", "15m", "5m", "3m", "1m"]
        parts = [f"{tf}:{tf_alignment.get(tf, 'N/A')}" for tf in ordered if tf in tf_alignment]
        return "|".join(parts)

    def record_outcome(
        self, tf_alignment: Dict[str, str], confluence_score: float,
        pnl_pct: float, timestamp: int
    ):
        """Record trade outcome for a multi-TF pattern."""
        sig = self.make_signature(tf_alignment)

        if sig not in self._patterns:
            self._patterns[sig] = MultiTFPattern(
                hash_key=sig, alignment_signature=sig
            )

        p = self._patterns[sig]
        p.total_trades += 1
        p.total_pnl += pnl_pct
        p.avg_confluence_score = (
            (p.avg_confluence_score * (p.total_trades - 1) + confluence_score) / p.total_trades
        )
        p.last_updated_ts = timestamp

        if pnl_pct > 0.1:
            p.wins += 1
        elif pnl_pct < -0.1:
            p.losses += 1

        self._save()
        logger.info(
            f"[MTF-RIVER] Recorded: {sig[:50]} | "
            f"PnL={pnl_pct:+.2f}% | WR={p.win_rate:.1%} | N={p.total_trades}"
        )

    def should_enter(
        self, tf_alignment: Dict[str, str], confluence_score: float
    ) -> Tuple[bool, float]:
        """Check if this multi-TF pattern is historically profitable."""
        sig = self.make_signature(tf_alignment)

        if sig not in self._patterns:
            return False, 0.0

        p = self._patterns[sig]
        if p.total_trades < self._min_samples:
            return False, p.confidence * 0.5

        conf = p.confidence
        should = conf >= self._min_confidence and p.win_rate >= 0.40

        return should, conf

    def get_top_patterns(self, limit: int = 10) -> List[MultiTFPattern]:
        return sorted(
            [p for p in self._patterns.values() if p.total_trades >= self._min_samples],
            key=lambda x: x.confidence, reverse=True
        )[:limit]

    def summary(self) -> dict:
        return {
            "total_patterns": len(self._patterns),
            "learned_patterns": sum(1 for p in self._patterns.values() if p.total_trades >= self._min_samples),
            "top_patterns": [
                {"sig": p.alignment_signature[:60], "wr": p.win_rate,
                 "trades": p.total_trades, "conf": p.confidence}
                for p in self.get_top_patterns(5)
            ]
        }

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._save_path) or ".", exist_ok=True)
            data = {k: vars(v) for k, v in self._patterns.items()}
            with open(self._save_path, "w") as f:
                json.dump(data, f, default=str)
        except Exception as e:
            logger.error(f"[MTF-RIVER] Save failed: {e}")

    def _load(self):
        try:
            if os.path.exists(self._save_path):
                with open(self._save_path) as f:
                    data = json.load(f)
                for k, v in data.items():
                    self._patterns[k] = MultiTFPattern(**v)
                logger.info(f"[MTF-RIVER] Loaded {len(self._patterns)} patterns")
        except Exception as e:
            logger.warning(f"[MTF-RIVER] Load failed: {e}")
