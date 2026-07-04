"""
STLine Aggregator
Collects ALL active ST lines from all timeframes.
Finds confluence zones where lines from multiple TFs cluster.
"""
import logging
from typing import List, Dict
from multi_tf_bot.models import STLineRecord, ConfluenceZone, TFAnalysisSnapshot

logger = logging.getLogger(__name__)


class STLineAggregator:
    """
    Collects and clusters ST lines across timeframes.
    Identifies price zones where multiple TFs have structural levels.
    """

    def __init__(self, tolerance_pct: float = 0.003):
        self.tolerance_pct = tolerance_pct

    def collect_all_active_lines(
        self, snapshots: Dict[str, TFAnalysisSnapshot]
    ) -> List[STLineRecord]:
        """Collect all active ST lines from all TF snapshots."""
        all_lines = []
        for tf, snap in snapshots.items():
            for line in snap.st_lines:
                if line.is_active:
                    all_lines.append(line)
        return all_lines

    def find_confluence_zones(
        self, snapshots: Dict[str, TFAnalysisSnapshot]
    ) -> List[ConfluenceZone]:
        """
        Find price zones where ST lines from multiple TFs cluster.
        Groups lines by price proximity (within tolerance_pct).
        Returns zones sorted by strength (TF count).
        """
        all_lines = self.collect_all_active_lines(snapshots)
        if not all_lines:
            return []

        bullish_lines = [l for l in all_lines if l.direction == "BULLISH"]
        bearish_lines = [l for l in all_lines if l.direction == "BEARISH"]

        zones = []
        zones.extend(self._cluster_lines(bullish_lines, "BULLISH"))
        zones.extend(self._cluster_lines(bearish_lines, "BEARISH"))

        zones.sort(key=lambda z: z.strength, reverse=True)
        return zones

    def _cluster_lines(
        self, lines: List[STLineRecord], direction: str
    ) -> List[ConfluenceZone]:
        """Cluster lines of same direction by price proximity."""
        if not lines:
            return []

        sorted_lines = sorted(lines, key=lambda l: l.price)
        clusters = []
        current_cluster = [sorted_lines[0]]

        for line in sorted_lines[1:]:
            ref_price = current_cluster[0].price
            if abs(line.price - ref_price) / ref_price <= self.tolerance_pct:
                current_cluster.append(line)
            else:
                clusters.append(current_cluster)
                current_cluster = [line]
        clusters.append(current_cluster)

        zones = []
        for cluster in clusters:
            unique_tfs = list(set(l.timeframe for l in cluster))
            prices = [l.price for l in cluster]

            zone = ConfluenceZone(
                price_center=sum(prices) / len(prices),
                price_low=min(prices),
                price_high=max(prices),
                direction=direction,
                tf_count=len(unique_tfs),
                timeframes=unique_tfs,
                line_ids=[l.id for l in cluster],
                strength=self._calculate_zone_strength(cluster, unique_tfs),
            )
            zones.append(zone)

        return zones

    def _calculate_zone_strength(
        self, cluster: List[STLineRecord], unique_tfs: List[str]
    ) -> float:
        """
        Zone strength = (TF diversity x valid ratio x point weight)
        Max 1.0
        """
        tf_diversity = min(len(unique_tfs) / 4.0, 1.0)
        valid_count = sum(1 for l in cluster if l.is_valid)
        valid_ratio = valid_count / len(cluster) if cluster else 0
        avg_points = sum(l.point_count for l in cluster) / len(cluster) if cluster else 0
        point_weight = min(avg_points / 10.0, 1.0)

        strength = (tf_diversity * 0.5) + (valid_ratio * 0.3) + (point_weight * 0.2)
        return min(strength, 1.0)

    def get_nearest_zone(
        self, zones: List[ConfluenceZone], price: float, direction: str
    ) -> ConfluenceZone:
        """Find nearest confluence zone to current price for given direction."""
        matching = [z for z in zones if z.direction == direction]
        if not matching:
            return None
        return min(matching, key=lambda z: abs(z.price_center - price))
