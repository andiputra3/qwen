"""
Multi-TF Orchestrator - PHASE 3 FINAL
Complete bot: DataFeed -> Pipeline -> Confluence -> Decision -> Executor -> River -> Dashboard
"""
import asyncio
import json
import logging
from pathlib import Path
from decimal import Decimal

from multi_tf_bot.tf_data_feed import MultiTFDataFeed
from multi_tf_bot.tf_pipeline_manager import TFPipelineManager
from multi_tf_bot.confluence_engine import ConfluenceEngine
from multi_tf_bot.multi_tf_decision import MultiTFDecisionMaker
from multi_tf_bot.multi_tf_river import MultiTFRiver
from multi_tf_bot.trade_executor import TradeExecutor
from multi_tf_bot.adaptive_update_handler import AdaptiveUpdateHandler
from multi_tf_bot.performance_tracker import PerformanceTracker
from multi_tf_bot.dashboard_server import DashboardDataStore, start_dashboard_server
from multi_tf_bot.state_exporter import StateExporter
from multi_tf_bot.models import MultiTFState, TradeDecision

logger = logging.getLogger(__name__)


class MultiTFOrchestrator:
    def __init__(self, config_path: str = "multi_tf_bot/config.json"):
        self.config = self._load_config(config_path)
        self.symbol = self.config["symbol"]
        self.timeframes = self.config["timeframes"]

        # Phase 1: Data + Analysis
        self.feed = MultiTFDataFeed(self.symbol, self.timeframes)
        self.pipeline_mgr = TFPipelineManager(self.timeframes)
        self.state = MultiTFState()

        # Phase 2: Confluence + Decision + River
        self.confluence_engine = ConfluenceEngine(self.config)
        self.decision_maker = MultiTFDecisionMaker(self.config)
        self.river = MultiTFRiver()

        # Phase 3: Execution + Adaptive + Performance + Dashboard
        self.trade_executor = TradeExecutor(
            account_balance=Decimal(str(self.config.get("account_balance", 10000))),
            leverage=self.config.get("leverage", 10),
        )
        self.adaptive_handler = AdaptiveUpdateHandler(self.config)
        self.performance_tracker = PerformanceTracker()
        self.dashboard_store = DashboardDataStore()
        self.state_exporter = StateExporter(
            output_dir="data/multi_tf_state",
            symbol=self.config.get("symbol", "BTCUSDT"),
        )

        # Wire callbacks
        self.trade_executor.on_trade_closed = self._on_trade_closed
        self.feed.on_candle = self._on_candle_received

        self._periodic_counter = 0
        self._last_confluence = None
        self._last_decision = None

    def _load_config(self, path: str) -> dict:
        p = Path(path)
        if p.exists():
            with open(p) as f:
                return json.load(f)
        raise FileNotFoundError(f"Config not found: {path}")

    async def start(self):
        logger.info("=" * 60)
        logger.info("  MULTI-TF CONFLUENCE BOT - PHASE 3 FINAL")
        logger.info("=" * 60)
        logger.info(f"  Symbol:     {self.symbol}")
        logger.info(f"  Timeframes: {len(self.timeframes)} ({', '.join(self.timeframes)})")
        logger.info(f"  Mode:       {self.config.get('mode', 'LONG_ONLY')}")
        logger.info(f"  Balance:    ${self.config.get('account_balance', 10000)}")
        logger.info(f"  Leverage:   {self.config.get('leverage', 10)}x")
        logger.info("=" * 60)

        if self.config.get("dashboard_enabled", False):
            port = self.config.get("dashboard_port", 8080)
            start_dashboard_server(port, self.dashboard_store)

        await self.feed.start()

    def _on_candle_received(self, timeframe: str, candle_data: dict):
        loop = asyncio.get_running_loop()
        asyncio.ensure_future(self._async_process_candle(timeframe, candle_data))

    async def _async_process_candle(self, timeframe: str, candle_data: dict):
        snapshot = await asyncio.to_thread(
            self.pipeline_mgr.process_candle, timeframe, candle_data
        )
        if snapshot is None:
            return

        self.state.snapshots[timeframe] = snapshot
        self.state.total_candles_processed += 1

        # Export state to JSON on every candle
        await asyncio.to_thread(self._export_state, timeframe)

        changed_tfs = self.adaptive_handler.check_structural_changes(self.state.snapshots)

        should_analyze = len(changed_tfs) > 0
        self._periodic_counter += 1
        if not should_analyze:
            check_interval = self.config.get("periodic_check_interval_candles", 5)
            if self._periodic_counter % check_interval == 0:
                should_analyze = True

        if should_analyze:
            current_price = candle_data["close"]
            await asyncio.to_thread(self._run_full_pipeline, current_price)

    def _run_full_pipeline(self, current_price: float):
        """Complete pipeline: Confluence -> Decision -> Execute -> Adaptive Check."""
        if not self.state.all_tfs_ready(self.timeframes):
            return

        # 1. Confluence Analysis
        confluence = self.confluence_engine.analyze(self.state.snapshots, current_price)
        self.state.last_confluence_ts = confluence.timestamp

        # 2. Check if should force-exit existing position
        if self.trade_executor.open_trade:
            should_exit, reason = self.adaptive_handler.should_force_exit_for_direction(
                confluence, self.trade_executor.open_trade.direction.value
            )
            if should_exit:
                logger.warning(f"[ORCH] Force exit: {reason}")
                self.trade_executor.force_exit(reason, current_price, confluence.timestamp)
                return

        # 3. River Check
        river_should, river_conf = self.river.should_enter(
            confluence.tf_alignment, confluence.confluence_score
        )

        # 4. Decision
        decision = self.decision_maker.evaluate(
            confluence=confluence,
            current_price=current_price,
            river_should_enter=river_should,
            river_confidence=river_conf,
            snapshots=self.state.snapshots,
        )

        self.state.last_decision = decision

        # 5. Execute if approved
        if decision.should_trade and not self.trade_executor.open_trade:
            self.trade_executor.execute_decision(decision)

        # 6. Check exit conditions
        if self.trade_executor.open_trade:
            self.trade_executor.check_exit(current_price, confluence.timestamp)

        # 7. Update dashboard
        self._update_dashboard(confluence, decision)

        # 8. Export state with confluence and decision
        self._last_confluence = confluence
        self._last_decision = decision
        self._export_state_full()

    def _export_state(self, timeframe: str):
        """Export TF snapshot after candle processing."""
        snap = self.state.snapshots.get(timeframe)
        if snap:
            self.state_exporter.export_tf_snapshot(snap)
            self.state_exporter.export_all_st_lines(self.state.snapshots)
            self.state_exporter.export_global_state(
                self.state, self._last_confluence, self._last_decision
            )

    def _export_state_full(self):
        """Full export including all snapshots, lines, and global state."""
        for tf, snap in self.state.snapshots.items():
            self.state_exporter.export_tf_snapshot(snap)
        self.state_exporter.export_all_st_lines(self.state.snapshots)
        self.state_exporter.export_global_state(
            self.state, self._last_confluence, self._last_decision
        )

    def _on_trade_closed(self, pnl_pct: float, timestamp: int):
        """Called when trade closes. Feed to River and Performance Tracker."""
        last_dec = self.state.last_decision
        trade_data = {
            "entry_ts": last_dec.timestamp if last_dec else timestamp,
            "exit_ts": timestamp,
            "direction": last_dec.direction if last_dec else "UNKNOWN",
            "entry_price": last_dec.entry_zone_low if last_dec else 0,
            "exit_price": None,
            "pnl_pct": pnl_pct,
            "pnl_usd": pnl_pct * float(self.trade_executor.account_balance) / 100,
            "duration_candles": 0,
            "reason": "TRADE_CLOSED",
        }
        self.performance_tracker.record_trade(trade_data, timestamp)

        if last_dec and last_dec.confluence:
            self.river.record_outcome(
                tf_alignment=last_dec.confluence.tf_alignment,
                confluence_score=last_dec.confluence.confluence_score,
                pnl_pct=pnl_pct,
                timestamp=timestamp,
            )

    def _update_dashboard(self, confluence, decision):
        """Update dashboard data store."""
        self.dashboard_store.update("state", self.state.summary())
        self.dashboard_store.update("metrics", self.performance_tracker.get_metrics())
        self.dashboard_store.update("recent_trades", self.performance_tracker.get_recent_trades(10))
        self.dashboard_store.update("confluence", confluence.to_dict() if confluence else {})
        self.dashboard_store.update("river_patterns", self.river.get_top_patterns(10))
        self.dashboard_store.update("structural_changes", self.adaptive_handler.get_change_history(20))

    def stop(self):
        self._export_state_full()
        self.feed.stop()
        logger.info("[ORCH] Stopped")
        logger.info(f"[ORCH] Final Balance: ${self.trade_executor.account_balance:.2f}")
        logger.info(f"[ORCH] Total Trades: {len(self.trade_executor.trade_history)}")
