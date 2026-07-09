"""
Multi-TF Decision Maker - POST-AUDIT FIXED VERSION
Fix #3 Integration: Uses higher-TF weight check
Fix #4: Extended guard line fallback chain (4h->1h->30m->15m + expanding tolerance)
"""
import logging
from typing import Optional, Dict
from multi_tf_bot.models import ConfluenceResult, TradeDecision, TFAnalysisSnapshot

logger = logging.getLogger(__name__)


class MultiTFDecisionMaker:
    def __init__(self, config: dict):
        self.strong_threshold = config.get("confluence_thresholds", {}).get("strong", 0.60)
        self.moderate_threshold = config.get("confluence_thresholds", {}).get("moderate", 0.45)
        self.weak_threshold = config.get("confluence_thresholds", {}).get("weak", 0.30)
        self.min_tf_aligned = config.get("min_tf_aligned", 2)
        self.mode = config.get("mode", "LONG_ONLY")
        self.tf_weights = config.get("tf_weights", {})

    def evaluate(self, confluence: ConfluenceResult, current_price: float,
                 river_should_enter: bool = False, river_confidence: float = 0.0,
                 snapshots: Dict[str, TFAnalysisSnapshot] = None) -> TradeDecision:

        if confluence.tf_count_aligned < self.min_tf_aligned:
            return self._reject(
                confluence,
                f"INSUFFICIENT_ALIGNMENT ({confluence.tf_count_aligned}<{self.min_tf_aligned})"
            )

        if not confluence.conflict_detected and confluence.dominant_direction != "NEUTRAL":
            higher_tfs = {"15m", "30m", "1h", "4h"}
            higher_weight = sum(
                self.tf_weights.get(tf, 0.0)
                for tf, d in confluence.tf_alignment.items()
                if d == confluence.dominant_direction and tf in higher_tfs
            )
            if higher_weight < 0.15:
                return self._reject(confluence, f"NO_HIGHER_TF_ALIGN (W={higher_weight:.2f}<0.15)")

        if confluence.conflict_detected:
            return self._reject(confluence, "CONFLICT_DETECTED")

        if confluence.dominant_direction == "NEUTRAL":
            return self._reject(confluence, "NEUTRAL_DIRECTION")

        if self.mode == "LONG_ONLY" and confluence.dominant_direction != "BULLISH":
            return self._reject(confluence, f"MODE_FILTER (mode={self.mode})")
        if self.mode == "SHORT_ONLY" and confluence.dominant_direction != "BEARISH":
            return self._reject(confluence, f"MODE_FILTER (mode={self.mode})")

        if confluence.confluence_score < self.weak_threshold:
            return self._reject(
                confluence,
                f"LOW_CONFLUENCE ({confluence.confluence_score:.3f}<{self.weak_threshold})"
            )

        if river_confidence > 0.3 and not river_should_enter:
            return self._reject(confluence, f"RIVER_OVERRIDE (conf={river_confidence:.3f})")

        direction = confluence.dominant_direction
        score = confluence.confluence_score

        if score >= self.strong_threshold:
            size_pct = 100.0
        elif score >= self.moderate_threshold:
            size_pct = 65.0
        else:
            size_pct = 35.0

        entry_low, entry_high, sl, tp, guard_id, guard_tf = self._calculate_levels(
            confluence, current_price, direction, snapshots
        )

        final_confidence = score * 0.7 + river_confidence * 0.3

        decision = TradeDecision(
            timestamp=confluence.timestamp, should_trade=True, direction=direction,
            confidence=round(final_confidence, 4), entry_zone_low=entry_low,
            entry_zone_high=entry_high, stop_loss=sl, take_profit=tp,
            position_size_pct=size_pct, confluence=confluence,
            river_confidence=river_confidence, river_should_enter=river_should_enter,
            reasoning=f"APPROVED score={score:.3f} dir={direction} size={size_pct}%",
            guard_line_id=guard_id, guard_line_tf=guard_tf,
        )

        logger.info(
            f"[DECISION] TRADE {direction} | Conf={final_confidence:.3f} "
            f"Size={size_pct}% | Entry={entry_low}-{entry_high} SL={sl} TP={tp} Guard={guard_id}"
        )
        return decision

    def _calculate_levels(self, confluence, price, direction, snapshots):
        entry_low, entry_high, sl, tp = None, None, None, None
        guard_line_id, guard_line_tf = None, None

        for tf in ["4h", "1h", "30m", "15m"]:
            snap = snapshots.get(tf) if snapshots else None
            if not snap:
                continue
            target_price = snap.nearest_support if direction == "BULLISH" else snap.nearest_resistance
            if not target_price:
                continue
            for tolerance in [0.0005, 0.001, 0.002]:
                for line in snap.st_lines:
                    if line.is_active and abs(line.price - target_price) < (target_price * tolerance):
                        guard_line_id = line.id
                        guard_line_tf = tf
                        break
                if guard_line_id:
                    break
            if guard_line_id:
                break

        matching_zones = [z for z in confluence.zones if z.direction == direction]
        if matching_zones:
            best_zone = max(matching_zones, key=lambda z: z.strength)
            entry_low, entry_high = best_zone.price_low, best_zone.price_high
            sl = best_zone.price_low * 0.995 if direction == "BULLISH" else best_zone.price_high * 1.005
            tp = price + (price - sl) * 1.5 if direction == "BULLISH" else price - (sl - price) * 1.5
        elif guard_line_id and snapshots:
            snap = snapshots.get(guard_line_tf)
            if snap:
                if direction == "BULLISH":
                    entry_low = snap.nearest_support * 0.998 if snap.nearest_support else price * 0.998
                    entry_high = price
                    sl = snap.nearest_support * 0.995 if snap.nearest_support else price * 0.995
                else:
                    entry_low = price
                    entry_high = snap.nearest_resistance * 1.002 if snap.nearest_resistance else price * 1.002
                    sl = snap.nearest_resistance * 1.005 if snap.nearest_resistance else price * 1.005
                tp = price + (price - sl) * 1.5 if direction == "BULLISH" else price - (sl - price) * 1.5

        return entry_low, entry_high, sl, tp, guard_line_id, guard_line_tf

    def _reject(self, confluence: ConfluenceResult, reason: str) -> TradeDecision:
        return TradeDecision(
            timestamp=confluence.timestamp, should_trade=False,
            direction=confluence.dominant_direction,
            confidence=confluence.confluence_score, confluence=confluence,
            rejection_reason=reason, reasoning=f"REJECTED: {reason}",
        )
