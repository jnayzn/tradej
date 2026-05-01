"""MetaTrader 5 → Trading Journal bridge.

Pulls closed deals from a running MetaTrader 5 terminal and POSTs them to the
Trading Journal API as importable trade records. Designed to be run on the
Windows machine where MT5 is installed (the `MetaTrader5` Python package is
Windows-only).

Usage::

    python mt5_bridge.py --api-url http://localhost:8000/api --days 30

Optionally pre-authenticate to a specific account::

    python mt5_bridge.py --login 12345 --password "***" --server "ICMarkets-Demo"

The script is idempotent: deals are deduplicated by their MT5 ticket on the
server side, so re-running it is safe.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    import MetaTrader5 as mt5  # type: ignore
except ImportError:  # pragma: no cover — runtime-only Windows dep.
    mt5 = None  # type: ignore[assignment]

import requests

# Per the MT5 docs:
# DEAL_ENTRY_OUT (1) closes a position; DEAL_ENTRY_INOUT (2) reverses.
DEAL_ENTRY_OUT = 1
DEAL_ENTRY_INOUT = 2

# DEAL_TYPE_BUY = 0, DEAL_TYPE_SELL = 1.
DEAL_TYPE_BUY = 0
DEAL_TYPE_SELL = 1


def _position_order_type(opens: list[Any], close: Any) -> str:
    """Return the position direction (BUY/SELL).

    When at least one opening deal is in scope, its `type` matches the
    position direction directly. Otherwise we have to derive it from the
    closing deal, whose `type` is the *opposite* of the position direction in
    MT5 (a BUY position closes with a SELL deal, and vice versa).
    """
    if opens:
        return "BUY" if opens[0].type == DEAL_TYPE_BUY else "SELL"
    return "SELL" if close.type == DEAL_TYPE_BUY else "BUY"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--api-url", default="http://localhost:8000/api", help="Trading Journal API base URL.")
    p.add_argument("--days", type=int, default=30, help="Lookback window in days.")
    p.add_argument("--login", type=int, default=None, help="MT5 account login (optional).")
    p.add_argument("--password", default=None, help="MT5 account password (optional).")
    p.add_argument("--server", default=None, help="MT5 trade server, e.g. 'ICMarkets-Demo'.")
    p.add_argument("--terminal-path", default=None, help="Path to terminal64.exe.")
    p.add_argument("--dry-run", action="store_true", help="Print payload, do not POST.")
    return p.parse_args()


def _initialize_mt5(args: argparse.Namespace) -> None:
    if mt5 is None:
        sys.exit("MetaTrader5 package not installed. `pip install MetaTrader5` (Windows-only).")
    init_kwargs: dict[str, Any] = {}
    if args.terminal_path:
        init_kwargs["path"] = args.terminal_path
    if not mt5.initialize(**init_kwargs):
        sys.exit(f"mt5.initialize() failed: {mt5.last_error()}")
    if args.login and args.password and args.server:
        if not mt5.login(args.login, password=args.password, server=args.server):
            sys.exit(f"mt5.login() failed: {mt5.last_error()}")
    info = mt5.account_info()
    if info is not None:
        print(f"Connected to MT5 account #{info.login} on {info.server} ({info.currency}).")


def _build_trade_records(start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Convert MT5 deals into trade records ready for the API.

    MT5 records every fill as a "deal". A round-trip position is normally
    represented by an opening deal (DEAL_ENTRY_IN) and a closing deal
    (DEAL_ENTRY_OUT). We aggregate by `position_id` and emit one record per
    closed position, falling back to per-deal export when the open leg is
    outside the lookback window.
    """
    deals = mt5.history_deals_get(start, end) or []  # type: ignore[union-attr]
    by_position: dict[int, list[Any]] = {}
    for d in deals:
        by_position.setdefault(d.position_id, []).append(d)

    records: list[dict[str, Any]] = []
    for position_id, position_deals in by_position.items():
        position_deals.sort(key=lambda d: d.time)
        opens = [d for d in position_deals if d.entry == 0]
        closes = [d for d in position_deals if d.entry in (DEAL_ENTRY_OUT, DEAL_ENTRY_INOUT)]
        if not closes:
            continue
        # If the opening leg was before the lookback, fall back to the close-only data.
        opening = opens[0] if opens else closes[0]
        close = closes[-1]

        order_type = _position_order_type(opens, close)
        record: dict[str, Any] = {
            "ticket": int(position_id),
            "symbol": close.symbol,
            "type": order_type,
            "volume": float(opening.volume or close.volume),
            "open_time": datetime.fromtimestamp(opening.time, tz=timezone.utc).isoformat(),
            "close_time": datetime.fromtimestamp(close.time, tz=timezone.utc).isoformat(),
            "open_price": float(opening.price),
            "close_price": float(close.price),
            "profit": float(sum(getattr(d, "profit", 0) or 0 for d in closes)),
            "commission": float(sum(getattr(d, "commission", 0) or 0 for d in position_deals)),
            "swap": float(sum(getattr(d, "swap", 0) or 0 for d in position_deals)),
            "comment": getattr(close, "comment", "") or "",
            "magic_number": int(getattr(close, "magic", 0) or 0) or None,
        }
        records.append(record)
    return records


def _post_records(api_url: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    url = api_url.rstrip("/") + "/trades/import/"
    resp = requests.post(url, json={"trades": records}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    args = _parse_args()
    _initialize_mt5(args)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)
    print(f"Fetching deals from {start.isoformat()} → {end.isoformat()}…")
    records = _build_trade_records(start, end)
    print(f"Built {len(records)} trade record(s).")

    if args.dry_run:
        print(json.dumps(records, indent=2)[:4000])
        return

    if not records:
        print("Nothing to upload.")
        return
    result = _post_records(args.api_url, records)
    print(f"Server: {result}")


if __name__ == "__main__":
    main()
