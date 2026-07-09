"""
Dashboard Server - Phase 3 (Async Version)
Uses aiohttp for non-blocking HTTP API.
"""
import asyncio
import json
import logging
from typing import Dict, Any

from aiohttp import web

logger = logging.getLogger(__name__)


class DashboardDataStore:
    """Thread-safe data store for dashboard."""

    def __init__(self):
        self.data: Dict[str, Any] = {
            "state": {},
            "metrics": {},
            "recent_trades": [],
            "confluence": {},
            "river_patterns": [],
            "structural_changes": [],
        }

    def update(self, key: str, value: Any):
        self.data[key] = value

    def get_all(self) -> Dict:
        return dict(self.data)

    def get(self, key: str) -> Any:
        return self.data.get(key)


_store = DashboardDataStore()


DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Multi-TF Confluence Bot Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: #fff; }
        .card { background: #2a2a2a; padding: 15px; margin: 10px; border-radius: 8px; }
        .metric { font-size: 24px; font-weight: bold; color: #4CAF50; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #444; }
        th { background: #333; }
        .positive { color: #4CAF50; }
        .negative { color: #f44336; }
    </style>
</head>
<body>
    <h1>Multi-TF Confluence Bot Dashboard</h1>
    <div id="metrics"></div>
    <div id="trades"></div>
    <script>
        async function fetchData() {
            const res = await fetch('/api/state');
            const data = await res.json();
            document.getElementById('metrics').innerHTML = `
                <div class="card">
                    <h3>Performance Metrics</h3>
                    <div class="metric">Balance: $${(data.metrics || {}).current_balance || 10000}</div>
                    <p>Win Rate: ${(((data.metrics || {}).win_rate || 0) * 100).toFixed(1)}%</p>
                    <p>Profit Factor: ${(data.metrics || {}).profit_factor || 0}</p>
                    <p>Total Trades: ${(data.metrics || {}).total_trades || 0}</p>
                </div>`;
            document.getElementById('trades').innerHTML = `
                <div class="card">
                    <h3>Recent Trades</h3>
                    <table>
                        <tr><th>Direction</th><th>PnL %</th><th>Reason</th></tr>
                        ${(data.recent_trades || []).map(t => `
                            <tr>
                                <td>${t.direction}</td>
                                <td class="${t.pnl_pct >= 0 ? 'positive' : 'negative'}">${(t.pnl_pct || 0).toFixed(2)}%</td>
                                <td>${t.reason}</td>
                            </tr>`).join('')}
                    </table>
                </div>`;
        }
        fetchData();
        setInterval(fetchData, 5000);
    </script>
</body>
</html>"""


async def handle_root(request):
    return web.Response(text=DASHBOARD_HTML, content_type='text/html')


async def handle_api(request):
    endpoint = request.match_info.get('endpoint', '')
    if endpoint == 'state' or not endpoint:
        data = _store.get_all()
    else:
        data = _store.get(endpoint)
    return web.json_response(data)


def start_dashboard_server(port: int = 8080, data_store: DashboardDataStore = None):
    global _store
    if data_store:
        _store = data_store

    app = web.Application()
    app.router.add_get('/', handle_root)
    app.router.add_get('/api/{endpoint:.*}', handle_api)

    async def run_server():
        runner = web.AppRunner(app, handle_signals=False)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logger.info(f"[DASHBOARD] Async server started on http://localhost:{port}")

    asyncio.ensure_future(run_server())