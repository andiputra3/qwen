"""
Performance Tracker - Phase 3
Tracks real-time metrics: WR, PF, expectancy, max DD, equity curve.
Exports to JSON/CSV for dashboard.
"""
import json
import csv
import logging
from pathlib import Path
from typing import List, Dict
from decimal import Decimal

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """
    Tracks trading performance metrics in real-time.
    Uses MetricsCalculator (File #39) for comprehensive analysis.
    """

    def __init__(self, output_dir: str = "data/performance"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.trades: List[Dict] = []
        self.equity_curve: List[Dict] = []
        self.initial_balance: Decimal = Decimal("10000")
        self.current_balance: Decimal = Decimal("10000")

        self._metrics_file = self.output_dir / "metrics.json"
        self._trades_file = self.output_dir / "trades.csv"
        self._equity_file = self.output_dir / "equity.csv"

        self._init_csvs()

    def _init_csvs(self):
        if not self._trades_file.exists():
            with open(self._trades_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "entry_ts", "exit_ts", "direction", "entry_price", "exit_price",
                    "pnl_pct", "pnl_usd", "duration_candles", "reason"
                ])

        if not self._equity_file.exists():
            with open(self._equity_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "balance", "equity"])

    def record_trade(self, trade_data: Dict, timestamp: int):
        """Record completed trade and update metrics."""
        self.trades.append(trade_data)

        pnl_usd = Decimal(str(trade_data.get("pnl_usd", 0)))
        self.current_balance += pnl_usd

        self.equity_curve.append({
            "timestamp": timestamp,
            "balance": float(self.current_balance),
            "equity": float(self.current_balance),
        })

        with open(self._trades_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                trade_data.get("entry_ts", timestamp),
                trade_data.get("exit_ts", timestamp),
                trade_data.get("direction", ""),
                trade_data.get("entry_price", ""),
                trade_data.get("exit_price", ""),
                trade_data.get("pnl_pct", ""),
                trade_data.get("pnl_usd", ""),
                trade_data.get("duration_candles", ""),
                trade_data.get("reason", ""),
            ])

        with open(self._equity_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, float(self.current_balance), float(self.current_balance)])

        metrics = self.calculate_metrics()
        self._save_metrics(metrics)

        logger.info(
            f"[PERF] Trade #{len(self.trades)} | PnL={trade_data.get('pnl_pct', 0):+.2f}% | "
            f"Balance=${self.current_balance:.2f} | WR={metrics.get('win_rate', 0):.1%}"
        )

    def calculate_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics."""
        if not self.trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "profit_factor": 0,
                "expectancy": 0,
                "max_drawdown": 0,
                "current_balance": float(self.current_balance),
            }

        pnls = [float(t.get("pnl_pct", 0)) for t in self.trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        total = len(pnls)
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = win_count / total if total > 0 else 0

        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        avg_win = gross_profit / win_count if win_count > 0 else 0
        avg_loss = gross_loss / loss_count if loss_count > 0 else 0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        max_dd = 0
        peak = float(self.initial_balance)
        for eq in self.equity_curve:
            balance = eq["balance"]
            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        return {
            "total_trades": total,
            "wins": win_count,
            "losses": loss_count,
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 4) if profit_factor != float('inf') else None,
            "gross_profit": round(gross_profit, 4),
            "gross_loss": round(gross_loss, 4),
            "expectancy_pct": round(expectancy, 4),
            "max_drawdown_pct": round(max_dd * 100, 4),
            "avg_win_pct": round(avg_win, 4),
            "avg_loss_pct": round(avg_loss, 4),
            "current_balance": float(self.current_balance),
            "total_pnl_pct": round((float(self.current_balance) / float(self.initial_balance) - 1) * 100, 4),
        }

    def _save_metrics(self, metrics: Dict):
        with open(self._metrics_file, "w") as f:
            json.dump(metrics, f, indent=2)

    def get_metrics(self) -> Dict:
        return self.calculate_metrics()

    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        return self.trades[-limit:]

    def get_equity_curve(self, limit: int = 100) -> List[Dict]:
        return self.equity_curve[-limit:]
