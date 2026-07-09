"""
Dual River Engine v2.0 - CRASH-FIXED VERSION (P0-3)
Fix: Safe JSON load with corruption recovery. Backup rotation on save.
Prevents total learning loss from corrupt state file.
"""
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import json, os, shutil, logging

from st_lms_core.config.settings import CONFIG
from st_lms_core.core.models.enums import TradeOutcome
from st_lms_core.core.models.dual_river_models import EntryPattern, ExitPattern

logger = logging.getLogger(__name__)


class EntryRiver:
    def __init__(self):
        self._patterns: Dict[str, EntryPattern] = {}
        self._total_records: int = 0

    def record_entry(self, st_dir, wave_dir, wave_len, stack_priority,
                     compressed, macd, oi_state, outcome, pnl_pct, hold_candles, timestamp):
        wave_bucket = "SHORT" if wave_len < 5 else ("NORMAL" if wave_len <= 12 else "LONG")
        hash_key = f"{st_dir}|{wave_dir}|{wave_bucket}|{stack_priority}|{compressed}|{macd}|{oi_state}"

        if hash_key not in self._patterns:
            self._patterns[hash_key] = EntryPattern(
                hash_key=hash_key, st_direction=st_dir, wave_direction=wave_dir,
                wave_length_bucket=wave_bucket, stack_priority=stack_priority,
                compressed=compressed, macd_bucket=macd, oi_state=oi_state
            )

        p = self._patterns[hash_key]
        p.total_trades += 1
        p.total_pnl += pnl_pct
        p.avg_hold_candles = ((p.avg_hold_candles * (p.total_trades - 1) + hold_candles) / p.total_trades)
        p.last_updated_ts = timestamp

        if outcome == TradeOutcome.WIN:
            p.wins += 1
        elif outcome == TradeOutcome.LOSS:
            p.losses += 1

        if oi_state != "ABSENT":
            p.oi_on_trades += 1
            if outcome == TradeOutcome.WIN:
                p.oi_on_wins += 1
        else:
            p.oi_off_trades += 1
            if outcome == TradeOutcome.WIN:
                p.oi_off_wins += 1

        self._total_records += 1

    def should_enter(self, st_dir, wave_dir, wave_len, stack_priority,
                     compressed, macd, oi_state) -> Tuple[bool, float, Optional[dict]]:
        wave_bucket = "SHORT" if wave_len < 5 else ("NORMAL" if wave_len <= 12 else "LONG")
        hash_key = f"{st_dir}|{wave_dir}|{wave_bucket}|{stack_priority}|{compressed}|{macd}|{oi_state}"

        if hash_key not in self._patterns:
            return False, 0.0, None

        p = self._patterns[hash_key]
        if p.total_trades < CONFIG.river_min_samples:
            return False, 0.0, {"reason": "INSUFFICIENT_SAMPLES"}

        base_conf = p.confidence_score
        if oi_state != "ABSENT" and p.oi_on_trades >= 3:
            base_conf = base_conf * 0.6 + p.oi_on_win_rate * 0.4
        elif oi_state == "ABSENT" and p.oi_off_trades >= 3:
            base_conf = p.oi_off_win_rate * 0.6
        elif oi_state == "ABSENT":
            base_conf *= 0.5

        boost = 0.0
        if wave_len >= 8 and not compressed:
            boost += 0.08
        if stack_priority == "HIGH":
            boost += 0.06
        if macd in ("BULLISH", "BEARISH"):
            boost += 0.05
        if oi_state == "INCREASING":
            boost += 0.10
        elif oi_state == "DECREASING":
            boost -= 0.12

        final_conf = min(max(base_conf + boost, 0.0), 1.0)
        should = final_conf >= float(CONFIG.river_min_confidence) and p.win_rate >= 0.40

        stats = {
            "pattern_hash": hash_key, "total_trades": p.total_trades,
            "win_rate": p.win_rate, "profit_factor": p.profit_factor,
            "oi_on_wr": p.oi_on_win_rate, "oi_off_wr": p.oi_off_win_rate,
            "avg_hold": p.avg_hold_candles
        }
        return should, final_conf, stats

    def get_top_patterns(self, limit=10) -> List[EntryPattern]:
        return sorted(
            [p for p in self._patterns.values() if p.total_trades >= CONFIG.river_min_samples],
            key=lambda x: x.confidence_score, reverse=True
        )[:limit]

    @property
    def total_records(self) -> int:
        return self._total_records

    @property
    def unique_patterns(self) -> int:
        return len(self._patterns)

    def load_state(self, data: dict):
        for k, v in data.items():
            self._patterns[k] = EntryPattern(**v)

    def dump_state(self) -> dict:
        return {k: vars(v) for k, v in self._patterns.items()}


class ExitRiver:
    def __init__(self):
        self._patterns: Dict[str, ExitPattern] = {}
        self._total_records: int = 0

    def record_exit(self, entry_hash, exit_trigger, hold_candles, pnl_pct,
                    max_profit_pct, macd_at_exit, oi_at_exit, st_break_status, timestamp):
        hold_bucket = "EARLY" if hold_candles < 3 else ("MID" if hold_candles <= 8 else "LATE")
        pnl_bucket = "SMALL" if abs(pnl_pct) < 0.3 else ("MED" if abs(pnl_pct) <= 0.8 else "LARGE")
        hash_key = f"{entry_hash}|{exit_trigger}|{hold_bucket}|{pnl_bucket}|{st_break_status}"

        if hash_key not in self._patterns:
            self._patterns[hash_key] = ExitPattern(
                hash_key=hash_key, entry_pattern_hash=entry_hash,
                exit_trigger=exit_trigger, hold_candles_bucket=hold_bucket,
                pnl_bucket=pnl_bucket, macd_at_exit=macd_at_exit,
                oi_at_exit=oi_at_exit, st_break_status=st_break_status
            )

        p = self._patterns[hash_key]
        p.total_exits += 1
        p.avg_pnl = (p.avg_pnl * (p.total_exits - 1) + pnl_pct) / p.total_exits
        if abs(pnl_pct - max_profit_pct) < Decimal("0.1"):
            p.exits_at_peak += 1
        if pnl_pct < max_profit_pct * Decimal("0.5") and max_profit_pct > Decimal("0.5"):
            p.exits_too_early += 1
        if pnl_pct < Decimal("0") and max_profit_pct > Decimal("0.3"):
            p.exits_too_late += 1
        self._total_records += 1

    @property
    def total_records(self) -> int:
        return self._total_records

    def load_state(self, data: dict):
        for k, v in data.items():
            self._patterns[k] = ExitPattern(**v)

    def dump_state(self) -> dict:
        return {k: vars(v) for k, v in self._patterns.items()}


class DualRiverEngine:
    def __init__(self):
        self.entry_river = EntryRiver()
        self.exit_river = ExitRiver()
        self._active_trades: Dict[str, dict] = {}
        self._load_state()

    def on_entry(self, trade_id, context, entry_price, timestamp):
        self._active_trades[trade_id] = {
            "entry_ts": timestamp, "entry_price": entry_price,
            "context": context, "max_price": entry_price, "min_price": entry_price
        }

    def on_price_update(self, trade_id, high, low):
        if trade_id in self._active_trades:
            t = self._active_trades[trade_id]
            t["max_price"] = max(t["max_price"], high)
            t["min_price"] = min(t["min_price"], low)

    def on_exit(self, trade_id, exit_trigger, exit_price, macd_now, oi_now, st_break, timestamp):
        if trade_id not in self._active_trades:
            return
        t = self._active_trades[trade_id]
        ctx = t["context"]
        entry_px = t["entry_price"]

        if ctx["st_direction"] == "BULLISH":
            pnl = ((exit_price - entry_px) / entry_px) * 100
            max_prof = ((t["max_price"] - entry_px) / entry_px) * 100
        else:
            pnl = ((entry_px - exit_price) / entry_px) * 100
            max_prof = ((entry_px - t["min_price"]) / entry_px) * 100

        hold_candles = max(1, (timestamp - t["entry_ts"]) // 300000)
        outcome = (TradeOutcome.WIN if pnl > Decimal("0.2")
                   else TradeOutcome.LOSS if pnl < Decimal("-0.2")
                   else TradeOutcome.BREAKEVEN)

        entry_hash = (f"{ctx['st_direction']}|{ctx['wave_direction']}|"
                      f"{ctx.get('wave_length', 0)}|{ctx['stack_priority']}|"
                      f"{ctx['compressed']}|{ctx['macd']}|{ctx['oi_state']}")

        self.entry_river.record_entry(
            ctx["st_direction"], ctx["wave_direction"], ctx.get("wave_length", 0),
            ctx["stack_priority"], ctx["compressed"], ctx["macd"], ctx["oi_state"],
            outcome, pnl, hold_candles, timestamp
        )
        self.exit_river.record_exit(
            entry_hash, exit_trigger, hold_candles, pnl, max_prof,
            macd_now, oi_now, st_break, timestamp
        )
        del self._active_trades[trade_id]

        try:
            self._save_state()
        except Exception as e:
            logger.error(f"[DUAL-RIVER] Save failed post-exit: {e}. State in memory only.")

    def get_entry_recommendation(self, context):
        should, conf, stats = self.entry_river.should_enter(
            context["st_direction"], context["wave_direction"],
            context.get("wave_length", 0), context["stack_priority"],
            context["compressed"], context["macd"], context["oi_state"]
        )
        return {"should_enter": should, "confidence": conf, "stats": stats,
                "recommendation": "ENTER" if should else "WAIT"}

    def get_learning_summary(self):
        top = self.entry_river.get_top_patterns(5)
        return {
            "entry_records": self.entry_river.total_records,
            "exit_records": self.exit_river.total_records,
            "unique_entry_patterns": self.entry_river.unique_patterns,
            "active_trades": len(self._active_trades),
            "top_patterns": [
                {"pattern": p.hash_key[:50], "wr": p.win_rate, "pf": p.profit_factor,
                 "trades": p.total_trades, "oi_on_wr": p.oi_on_win_rate,
                 "oi_off_wr": p.oi_off_win_rate, "conf": p.confidence_score}
                for p in top
            ]
        }

    def _save_state(self):
        """Atomic save with backup rotation to prevent corruption."""
        save_path = CONFIG.river_save_path
        backup_path = save_path + ".bak"
        tmp_path = save_path + ".tmp"

        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)

        state = {
            "entry_patterns": self.entry_river.dump_state(),
            "exit_patterns": self.exit_river.dump_state(),
            "entry_records": self.entry_river.total_records,
            "exit_records": self.exit_river.total_records
        }

        with open(tmp_path, "w") as f:
            json.dump(state, f, default=str)

        if os.path.exists(save_path):
            shutil.copy2(save_path, backup_path)

        shutil.move(tmp_path, save_path)

    def _load_state(self):
        """Safe load with fallback to backup on corruption."""
        save_path = CONFIG.river_save_path
        backup_path = save_path + ".bak"

        for path, label in [(save_path, "main"), (backup_path, "backup")]:
            try:
                if not os.path.exists(path):
                    continue
                with open(path) as f:
                    state = json.load(f)
                self.entry_river.load_state(state.get("entry_patterns", {}))
                self.exit_river.load_state(state.get("exit_patterns", {}))
                self.entry_river._total_records = state.get("entry_records", 0)
                self.exit_river._total_records = state.get("exit_records", 0)
                logger.info(f"[DUAL-RIVER] Loaded {label} state: "
                            f"{self.entry_river.total_records} entries, "
                            f"{self.entry_river.unique_patterns} patterns")
                return
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(f"[DUAL-RIVER] {label} state corrupt ({e}), trying next...")
            except Exception as e:
                logger.warning(f"[DUAL-RIVER] {label} load failed ({e}), trying next...")

        logger.warning("[DUAL-RIVER] No valid state found. Starting fresh.")
