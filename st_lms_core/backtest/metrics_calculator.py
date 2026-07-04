"""
Metrics Calculator - Comprehensive performance metrics from trade history.
Sharpe ratio validity-gated (requires MIN_BARS_FOR_SHARPE).
"""
from decimal import Decimal
from typing import List, Dict
import math


class MetricsCalculator:
    MIN_BARS_FOR_SHARPE = 500

    @staticmethod
    def calculate(trades: List[Dict]) -> Dict:
        if not trades:
            return {"total_trades": 0}

        pnls = [float(t.get("pnl_pct", 0)) for t in trades]
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

        equity_curve = [0.0]
        for p in pnls:
            equity_curve.append(equity_curve[-1] + p)
        peak = equity_curve[0]
        max_dd = 0.0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = peak - eq
            if dd > max_dd:
                max_dd = dd

        if len(pnls) < MetricsCalculator.MIN_BARS_FOR_SHARPE:
            sharpe = None
            sharpe_valid = False
        else:
            mean_pnl = sum(pnls) / len(pnls)
            variance = sum((p - mean_pnl) ** 2 for p in pnls) / (len(pnls) - 1)
            std_dev = math.sqrt(variance) if variance > 0 else 0
            bars_per_year = 288 * 365
            sharpe = (mean_pnl / std_dev * math.sqrt(bars_per_year)) if std_dev > 0 else 0.0
            sharpe_valid = True

        return {
            "total_trades": total, "wins": win_count, "losses": loss_count,
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 4) if profit_factor != float('inf') else None,
            "gross_profit": round(gross_profit, 4), "gross_loss": round(gross_loss, 4),
            "expectancy_pct": round(expectancy, 4), "max_drawdown_pct": round(max_dd, 4),
            "sharpe_ratio": round(sharpe, 4) if sharpe is not None else None,
            "sharpe_valid": sharpe_valid,
            "avg_win_pct": round(avg_win, 4), "avg_loss_pct": round(avg_loss, 4),
            "min_bars_required": MetricsCalculator.MIN_BARS_FOR_SHARPE,
            "actual_bars": len(pnls),
        }
