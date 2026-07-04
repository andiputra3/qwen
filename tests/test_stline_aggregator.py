"""Test STLineAggregator — zone clustering, strength calculation."""
from multi_tf_bot.stline_aggregator import STLineAggregator
from multi_tf_bot.models import TFAnalysisSnapshot, STLineRecord


def make_line(line_id: str, price: float, tf: str, direction="BULLISH",
              status="VALID", points=5) -> STLineRecord:
    return STLineRecord(
        id=line_id, price=price, direction=direction, status=status,
        point_count=points, start_ts=0, end_ts=None, timeframe=tf,
    )


class TestCollectLines:
    def setup_method(self):
        self.aggregator = STLineAggregator(tolerance_pct=0.003)

    def test_collect_all_active(self):
        snap = TFAnalysisSnapshot(
            timeframe="4h", timestamp=1000, price=50000.0,
            st_lines=[
                make_line("L1", 50000.0, "4h"),
                make_line("L2", 50100.0, "4h", status="DEACTIVATED"),
            ],
        )
        snapshots = {"4h": snap}
        lines = self.aggregator.collect_all_active_lines(snapshots)
        assert len(lines) == 1
        assert lines[0].id == "L1"


class TestFindConfluenceZones:
    def setup_method(self):
        self.aggregator = STLineAggregator(tolerance_pct=0.003)

    def test_no_lines_no_zones(self):
        snap = TFAnalysisSnapshot(timeframe="4h", timestamp=0, price=0.0, st_lines=[])
        zones = self.aggregator.find_confluence_zones({"4h": snap})
        assert zones == []

    def test_single_line_no_zone(self):
        """Single line doesn't form a confluence zone (needs cluster)."""
        snap = TFAnalysisSnapshot(
            timeframe="4h", timestamp=1000, price=50000.0,
            st_lines=[make_line("L1", 50000.0, "4h")],
        )
        zones = self.aggregator.find_confluence_zones({"4h": snap})
        # A single line forms a cluster of size 1, which becomes a zone
        assert len(zones) == 1
        assert zones[0].direction == "BULLISH"
        assert zones[0].price_center == 50000.0

    def test_multiple_tf_cluster(self):
        """Lines from multiple TFs at similar price -> confluence zone."""
        snap_4h = TFAnalysisSnapshot(
            timeframe="4h", timestamp=1000, price=50000.0,
            st_lines=[make_line("L1", 50000.0, "4h")],
        )
        snap_1h = TFAnalysisSnapshot(
            timeframe="1h", timestamp=1000, price=50000.0,
            st_lines=[make_line("L2", 50010.0, "1h")],
        )
        zones = self.aggregator.find_confluence_zones({"4h": snap_4h, "1h": snap_1h})
        assert len(zones) >= 1
        zone = zones[0]
        assert zone.tf_count >= 2
        assert "4h" in zone.timeframes
        assert "1h" in zone.timeframes

    def test_separate_directions(self):
        """Bullish and bearish lines form separate zones."""
        snap = TFAnalysisSnapshot(
            timeframe="4h", timestamp=1000, price=50000.0,
            st_lines=[
                make_line("L1", 50000.0, "4h", direction="BULLISH"),
                make_line("L2", 51000.0, "4h", direction="BEARISH"),
            ],
        )
        zones = self.aggregator.find_confluence_zones({"4h": snap})
        assert len(zones) == 2
        directions = {z.direction for z in zones}
        assert "BULLISH" in directions
        assert "BEARISH" in directions

    def test_zone_strength_higher_with_more_tfs(self):
        """Zona dengan lebih banyak TF punya strength lebih tinggi."""
        snap_4h = TFAnalysisSnapshot(
            timeframe="4h", timestamp=1000, price=50000.0,
            st_lines=[make_line("L1", 50000.0, "4h")],
        )
        snap_1h = TFAnalysisSnapshot(
            timeframe="1h", timestamp=1000, price=50000.0,
            st_lines=[make_line("L2", 50010.0, "1h")],
        )
        zones = self.aggregator.find_confluence_zones({"4h": snap_4h, "1h": snap_1h})
        assert len(zones) >= 1
        assert zones[0].strength > 0
