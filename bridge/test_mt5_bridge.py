"""Unit tests for the MT5 bridge.

These tests exercise pure-Python helpers in `mt5_bridge.py` without the
Windows-only `MetaTrader5` package; that dependency is optional and the module
falls back to `mt5 = None` when missing.

Run from the `bridge/` directory::

    python -m unittest test_mt5_bridge
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from mt5_bridge import DEAL_TYPE_BUY, DEAL_TYPE_SELL, _position_order_type


def _deal(deal_type: int) -> SimpleNamespace:
    return SimpleNamespace(type=deal_type)


class PositionOrderTypeTests(unittest.TestCase):
    def test_uses_opening_deal_type_when_open_is_in_scope(self) -> None:
        opens = [_deal(DEAL_TYPE_BUY)]
        # Closing deal type is irrelevant when we have an opening leg.
        close = _deal(DEAL_TYPE_SELL)
        self.assertEqual(_position_order_type(opens, close), "BUY")

        opens = [_deal(DEAL_TYPE_SELL)]
        close = _deal(DEAL_TYPE_BUY)
        self.assertEqual(_position_order_type(opens, close), "SELL")

    def test_inverts_closing_deal_type_when_open_is_outside_lookback(self) -> None:
        # A BUY position closes with a SELL deal — and vice versa. When the
        # opening leg is missing, we have to invert the close-deal type.
        close = _deal(DEAL_TYPE_SELL)  # SELL deal closes a BUY position.
        self.assertEqual(_position_order_type([], close), "BUY")

        close = _deal(DEAL_TYPE_BUY)  # BUY deal closes a SELL position.
        self.assertEqual(_position_order_type([], close), "SELL")


if __name__ == "__main__":
    unittest.main()
