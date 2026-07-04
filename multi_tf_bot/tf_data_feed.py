"""
Multi-Timeframe Data Feed
Uses Binance Futures combined WebSocket stream for efficiency.
Handles: 1m, 3m, 5m, 15m, 30m, 1h, 4h klines + markPrice for OI.
Auto-reconnect with exponential backoff.
"""
import asyncio
import json
import logging
from decimal import Decimal
from typing import Dict, Callable, Optional, List

logger = logging.getLogger(__name__)

try:
    import websockets
except ImportError:
    websockets = None
    logger.warning("[FEED] websockets not installed. Run: pip install websockets")


class MultiTFDataFeed:
    WS_URL = "wss://fstream.binance.com/stream"
    MARK_PRICE_URL = "wss://fstream.binance.com/ws/{symbol}@markPrice@1s"

    OPEN_TIMEOUT = 10
    CLOSE_TIMEOUT = 5
    PING_INTERVAL = 20
    PING_TIMEOUT = 10

    def __init__(self, symbol: str, timeframes: List[str]):
        self.symbol = symbol.lower()
        self.timeframes = timeframes
        self._running = False
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 30.0

        self.on_candle: Optional[Callable] = None
        self.on_oi: Optional[Callable] = None

    def _build_streams_param(self) -> str:
        streams = "/".join([
            f"{self.symbol}@kline_{tf}" for tf in self.timeframes
        ])
        return streams

    async def start(self):
        """Start combined kline stream + separate markPrice stream."""
        if websockets is None:
            logger.error("[FEED] Cannot start: websockets not installed")
            return

        self._running = True

        while self._running:
            try:
                logger.info(f"[FEED] Connecting to {len(self.timeframes)} TF streams...")

                kline_task = asyncio.create_task(self._kline_stream())
                mark_task = asyncio.create_task(self._mark_price_stream())

                await asyncio.gather(kline_task, mark_task)

            except Exception as e:
                logger.error(f"[FEED] Connection error: {e}")
                await self._backoff()

    async def _kline_stream(self):
        streams = self._build_streams_param()
        url = f"{self.WS_URL}?streams={streams}"

        async with websockets.connect(
            url,
            open_timeout=self.OPEN_TIMEOUT,
            close_timeout=self.CLOSE_TIMEOUT,
            ping_interval=self.PING_INTERVAL,
            ping_timeout=self.PING_TIMEOUT,
        ) as ws:
            logger.info(f"[FEED] Kline stream connected: {streams}")
            self._reconnect_delay = 1.0

            async for message in ws:
                if not self._running:
                    break

                try:
                    data = json.loads(message)
                    stream = data.get("stream", "")
                    payload = data.get("data", {})

                    if "@kline_" in stream:
                        tf = stream.split("@kline_")[1]
                        k = payload.get("k", {})

                        if k.get("x"):
                            candle_data = {
                                "timeframe": tf,
                                "timestamp": k["t"],
                                "open": Decimal(k["o"]),
                                "high": Decimal(k["h"]),
                                "low": Decimal(k["l"]),
                                "close": Decimal(k["c"]),
                                "volume": Decimal(k["v"]),
                                "is_closed": True,
                            }
                            if self.on_candle:
                                self.on_candle(tf, candle_data)
                except Exception as e:
                    logger.warning(f"[FEED] Parse error: {e}")

    async def _mark_price_stream(self):
        url = self.MARK_PRICE_URL.format(symbol=self.symbol)

        async with websockets.connect(
            url,
            open_timeout=self.OPEN_TIMEOUT,
            close_timeout=self.CLOSE_TIMEOUT,
            ping_interval=self.PING_INTERVAL,
            ping_timeout=self.PING_TIMEOUT,
        ) as ws:
            logger.info(f"[FEED] Mark price stream connected")

            async for message in ws:
                if not self._running:
                    break

                try:
                    data = json.loads(message)
                except Exception as e:
                    logger.warning(f"[FEED] Mark price parse error: {e}")

    async def _backoff(self):
        logger.info(f"[FEED] Reconnecting in {self._reconnect_delay:.1f}s...")
        await asyncio.sleep(self._reconnect_delay)
        self._reconnect_delay = min(
            self._reconnect_delay * 2, self._max_reconnect_delay
        )

    def stop(self):
        self._running = False
        logger.info("[FEED] Stopping...")
