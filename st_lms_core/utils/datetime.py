"""
DateTime Utilities - Dual Timezone Support (UTC + WIB).
Zero impact on trading logic. Pipeline uses epoch_ms internally.
Conversion only happens at reporting layer.
"""
from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))
UTC = timezone.utc


def format_dual_ts(epoch_ms: int) -> dict:
    """Convert epoch ms to dual timezone dict for reports."""
    dt_utc = datetime.fromtimestamp(epoch_ms / 1000, tz=UTC)
    dt_wib = datetime.fromtimestamp(epoch_ms / 1000, tz=WIB)
    return {
        "ts_ms": epoch_ms,
        "utc": dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "wib": dt_wib.strftime("%Y-%m-%d %H:%M:%S WIB")
    }


def format_dual_ts_short(epoch_ms: int) -> str:
    """Compact: 'HH:MM UTC | HH:MM WIB' for table rows."""
    dt_utc = datetime.fromtimestamp(epoch_ms / 1000, tz=UTC)
    dt_wib = datetime.fromtimestamp(epoch_ms / 1000, tz=WIB)
    return f"{dt_utc.strftime('%H:%M')} UTC | {dt_wib.strftime('%H:%M')} WIB"
