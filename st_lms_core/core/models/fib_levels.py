"""
Fibonacci Levels Model - FINAL AUDITED VERSION (Fix #1)
Direction-aware calculation: BULLISH and BEARISH waves produce correct levels.
Levels normalized so level_382 < level_618 for universal entry zone checks.
"""
from decimal import Decimal
from dataclasses import dataclass


@dataclass(frozen=True)
class FibLevels:
    level_000: Decimal
    level_236: Decimal
    level_382: Decimal
    level_500: Decimal
    level_618: Decimal
    level_786: Decimal
    level_100: Decimal
    exit_c_long: Decimal
    exit_c_short: Decimal
    direction: str

    @classmethod
    def from_wave(cls, start_price: Decimal, end_price: Decimal, direction: str) -> "FibLevels":
        """
        Direction-aware Fibonacci calculation.
        BULLISH: 0.000 = start (low), 1.000 = end (high)
        BEARISH: 0.000 = start (high), 1.000 = end (low)
        """
        diff = end_price - start_price

        raw = {
            "000": start_price,
            "236": start_price + diff * Decimal("0.236"),
            "382": start_price + diff * Decimal("0.382"),
            "500": start_price + diff * Decimal("0.500"),
            "618": start_price + diff * Decimal("0.618"),
            "786": start_price + diff * Decimal("0.786"),
            "100": end_price,
        }

        l382 = min(raw["382"], raw["618"])
        l618 = max(raw["382"], raw["618"])

        return cls(
            level_000=raw["000"],
            level_236=raw["236"],
            level_382=l382,
            level_500=raw["500"],
            level_618=l618,
            level_786=raw["786"],
            level_100=raw["100"],
            exit_c_long=raw["618"] if direction == "BULLISH" else raw["382"],
            exit_c_short=raw["382"] if direction == "BEARISH" else raw["618"],
            direction=direction,
        )
