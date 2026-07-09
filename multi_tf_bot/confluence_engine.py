"""
Confluence Engine - POST-AUDIT FIXED VERSION
Fix #3: Higher-TF weight floor prevents micro-TF-only signals
Fix #7: Warmup score normalization prevents inflation during partial TF coverage
Philosophy compliant: Trend remains sole Authority.
"""
import logging
from typing import Dict, List
from multi_tf_bot.models import TFAnalysisSnapshot, ConfluenceResult
from multi_tf_bot.stline_aggregator import STLineAggregator

logger = logging.getLogger(__name__)


class ConfluenceEngine:
    HIGHER_TF_MIN_WEIGHT = 0.15

    def __init__(self, config: dict):
        self.tf_weights = config.get("tf_weights", {})
        self.strong_threshold = config.get("confluence_thresholds", {}).get("strong", 0.60)
        self.moderate_threshold = config.get("confluence_thresholds", {}).get("moderate", 0.45)
        self.conflict_penalty = config.get("conflict_penalty", 0.5)
        self.alignment_bonus = config.get("alignment_bonus", 1.15)
        self.min_tf_aligned = config.get("min_tf_aligned", 2)
        self.warmup_min_tfs = config.get("warmup_min_tfs", 3)
        self.aggregator = STLineAggregator(
            tolerance_pct=config.get("st_line_tolerance_pct", 0.003)
        )

    def analyze(self, snapshots: Dict[str, TFAnalysisSnapshot], current_price: float) -> ConfluenceResult:
        tf_alignment = self._get_tf_alignment(snapshots)
        confluence_score, dominant_dir, conflict = self._score_alignment(tf_alignment)
        zones = self.aggregator.find_confluence_zones(snapshots)

        aligned_count = sum(1 for d in tf_alignment.values() if d == dominant_dir)
        weighted_aligned = sum(
            self.tf_weights.get(tf, 0.1)
            for tf, d in tf_alignment.items() if d == dominant_dir
        )

        reasoning = self._build_reasoning(
            tf_alignment, dominant_dir, confluence_score, zones, aligned_count, weighted_aligned
        )

        result = ConfluenceResult(
            timestamp=max((s.timestamp for s in snapshots.values()), default=0),
            price=current_price,
            confluence_score=confluence_score,
            dominant_direction=dominant_dir,
            tf_alignment=tf_alignment,
            zones=zones,
            conflict_detected=conflict,
            reasoning=reasoning,
            tf_count_aligned=aligned_count,
            total_tf_evaluated=len(snapshots),
        )

        logger.info(
            f"[CONFLUENCE] Score={confluence_score:.3f} Dir={dominant_dir} "
            f"Aligned={aligned_count}/{len(snapshots)} W={weighted_aligned:.2f} Conflict={conflict}"
        )
        return result

    def is_warmup_sufficient(self, snapshots: Dict[str, TFAnalysisSnapshot]) -> bool:
        return len(snapshots) >= self.warmup_min_tfs

    def is_alignment_sufficient(self, tf_alignment: Dict[str, str], dominant: str) -> bool:
        higher_tfs = {"15m", "30m", "1h", "4h"}
        higher_aligned_weight = sum(
            self.tf_weights.get(tf, 0.0)
            for tf, d in tf_alignment.items()
            if d == dominant and tf in higher_tfs
        )
        return higher_aligned_weight >= self.HIGHER_TF_MIN_WEIGHT

    def _get_tf_alignment(self, snapshots: Dict[str, TFAnalysisSnapshot]) -> Dict[str, str]:
        alignment = {}
        for tf, snap in snapshots.items():
            alignment[tf] = self._tf_direction(snap)
        return alignment

    def _tf_direction(self, snap: TFAnalysisSnapshot) -> str:
        if snap.trend_state == "UPTREND":
            return "BULLISH"
        if snap.trend_state == "DOWNTREND":
            return "BEARISH"
        if snap.wave_direction == "BULLISH" and snap.macd_bucket in ("BULLISH", "WEAKENING"):
            return "BULLISH"
        if snap.wave_direction == "BEARISH" and snap.macd_bucket in ("BEARISH", "WEAKENING"):
            return "BEARISH"
        return "NEUTRAL"

    def _score_alignment(self, tf_alignment: Dict[str, str]) -> tuple:
        bullish_score = 0.0
        bearish_score = 0.0
        total_weight = 0.0

        for tf, direction in tf_alignment.items():
            weight = self.tf_weights.get(tf, 0.1)
            total_weight += weight
            if direction == "BULLISH":
                bullish_score += weight
            elif direction == "BEARISH":
                bearish_score += weight

        if total_weight == 0:
            return 0.0, "NEUTRAL", False

        bull_pct = bullish_score / total_weight
        bear_pct = bearish_score / total_weight

        if bull_pct > bear_pct:
            dominant = "BULLISH"
            raw_score = bull_pct
        elif bear_pct > bull_pct:
            dominant = "BEARISH"
            raw_score = bear_pct
        else:
            return 0.0, "NEUTRAL", False

        conflict = False
        if bull_pct > 0.2 and bear_pct > 0.2:
            conflict = True
            raw_score *= self.conflict_penalty

        non_neutral = sum(1 for d in tf_alignment.values() if d != "NEUTRAL")
        aligned_with_dominant = sum(1 for d in tf_alignment.values() if d == dominant)
        if non_neutral > 0 and aligned_with_dominant == non_neutral:
            raw_score = min(raw_score * self.alignment_bonus, 1.0)

        total_possible_weight = sum(self.tf_weights.values())
        coverage_ratio = total_weight / total_possible_weight if total_possible_weight > 0 else 1.0
        if coverage_ratio < 0.7:
            raw_score *= coverage_ratio

        return round(raw_score, 4), dominant, conflict

    def _build_reasoning(self, alignment, dominant, score, zones, aligned_count, weighted_aligned):
        parts = []
        for tf in ["4h", "1h", "30m", "15m", "5m", "3m", "1m"]:
            if tf in alignment:
                parts.append(f"{tf}={alignment[tf][:4]}")
        zone_info = ""
        if zones:
            top = zones[0]
            zone_info = f" TopZone={top.price_center:.2f}({top.tf_count}TFs)"
        return f"[{', '.join(parts)}] Score={score:.2f} Aligned={aligned_count}(W={weighted_aligned:.2f}){zone_info}"
