"""MetaTrader 5 → Trading Journal bridge.

Pulls closed deals from a running MetaTrader 5 terminal and POSTs them to the
Trading Journal API as importable trade records. Designed to be run on the
Windows machine where MT5 is installed (the `MetaTrader5` Python package is
Windows-only).

Two modes are available:

**One-shot** (good for backfilling / scheduled tasks)::

    python mt5_bridge.py --api-url http://localhost:8000/api --days 30

**Watch** (long-running, near-real-time live sync)::

    python mt5_bridge.py --api-url http://localhost:8000/api --watch --interval 30

In watch mode the script polls MT5 every ``--interval`` seconds, posts only
records it has not seen before, and persists the highwater mark to
``--state-file`` so a restart does not re-scan the whole history. Server-side
deduplication by MT5 ticket means re-runs are always safe.

Optionally pre-authenticate to a specific account::

    python mt5_bridge.py --login 12345 --password "***" --server "ICMarkets-Demo"
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

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

DEFAULT_STATE_FILE = Path.home() / ".trading-journal-bridge.json"
# Re-scan a small window of already-seen trades on every tick to catch trades
# whose `close_time` lands exactly on the previous highwater mark, or trades
# whose profit was amended after the fact (rare, but possible).
WATCH_BACKFILL_SECONDS = 60

logger = logging.getLogger("mt5_bridge")


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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--api-url",
        default=os.environ.get("TRADING_JOURNAL_API_URL", "http://localhost:8000/api"),
        help="Trading Journal API base URL.",
    )
    p.add_argument(
        "--days",
        type=int,
        default=30,
        help="Lookback window in days (one-shot mode and first watch tick).",
    )
    p.add_argument(
        "--login", type=int, default=None, help="MT5 account login (optional)."
    )
    p.add_argument("--password", default=None, help="MT5 account password (optional).")
    p.add_argument(
        "--server", default=None, help="MT5 trade server, e.g. 'ICMarkets-Demo'."
    )
    p.add_argument("--terminal-path", default=None, help="Path to terminal64.exe.")
    p.add_argument("--dry-run", action="store_true", help="Print payload, do not POST.")
    p.add_argument(
        "--watch",
        action="store_true",
        help="Run continuously, polling MT5 every --interval seconds.",
    )
    p.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Watch-mode polling interval in seconds (default: 30).",
    )
    p.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_FILE,
        help=(
            "Where to persist the watch-mode highwater mark. Defaults to "
            f"{DEFAULT_STATE_FILE}."
        ),
    )
    p.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Max HTTP retry attempts on network errors (default: 5).",
    )
    return p.parse_args(argv)


def _initialize_mt5(args: argparse.Namespace) -> None:
    if mt5 is None:
        sys.exit(
            "MetaTrader5 package not installed. `pip install MetaTrader5` (Windows-only)."
        )
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
        logger.info(
            "Connected to MT5 account #%s on %s (%s).",
            info.login,
            info.server,
            info.currency,
        )


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
        closes = [
            d for d in position_deals if d.entry in (DEAL_ENTRY_OUT, DEAL_ENTRY_INOUT)
        ]
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
            "open_time": datetime.fromtimestamp(
                opening.time, tz=timezone.utc
            ).isoformat(),
            "close_time": datetime.fromtimestamp(
                close.time, tz=timezone.utc
            ).isoformat(),
            "open_price": float(opening.price),
            "close_price": float(close.price),
            "profit": float(sum(getattr(d, "profit", 0) or 0 for d in closes)),
            "commission": float(
                sum(getattr(d, "commission", 0) or 0 for d in position_deals)
            ),
            "swap": float(sum(getattr(d, "swap", 0) or 0 for d in position_deals)),
            "comment": getattr(close, "comment", "") or "",
            "magic_number": int(getattr(close, "magic", 0) or 0) or None,
        }
        records.append(record)
    return records


def _load_state(path: Path) -> dict[str, Any]:
    """Return the persisted watch-mode state, or an empty dict if absent.

    A corrupt state file is treated as "no state" — we log a warning and
    overwrite it on the next save. This keeps the daemon resilient to a
    half-written file from a hard kill.
    """
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("State file %s unreadable (%s); starting fresh.", path, exc)
        return {}


def _save_state(path: Path, state: dict[str, Any]) -> None:
    """Atomically persist `state` to `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    os.replace(tmp, path)


def _filter_new_records(
    records: list[dict[str, Any]],
    last_seen_close_time: str | None,
) -> list[dict[str, Any]]:
    """Drop records whose `close_time` is <= the highwater mark.

    The boundary is strictly less-than-or-equal so that a record matching the
    previous mark exactly (which was already POSTed) is filtered out. If two
    trades close in the same second, both are still picked up on the *next*
    tick because we widen the MT5 query window by ``WATCH_BACKFILL_SECONDS``.
    """
    if not last_seen_close_time:
        return list(records)
    return [r for r in records if r.get("close_time", "") > last_seen_close_time]


def _records_highwater(records: list[dict[str, Any]]) -> str | None:
    """Return the max `close_time` across `records`, or None if empty."""
    times = [r["close_time"] for r in records if r.get("close_time")]
    return max(times) if times else None


def _post_with_retry(
    api_url: str,
    records: list[dict[str, Any]],
    *,
    max_attempts: int = 5,
    base_backoff: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """POST `records` to the import endpoint with exponential backoff.

    Retries on `requests.RequestException` (network errors, timeouts,
    5xx via `raise_for_status`). 4xx errors are *not* retried — they
    indicate a malformed payload that won't fix itself.
    """
    url = api_url.rstrip("/") + "/trades/import/"
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(url, json={"trades": records}, timeout=30)
            if 400 <= resp.status_code < 500:
                resp.raise_for_status()  # surfaces a non-retryable HTTPError
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status is not None and 400 <= status < 500:
                # Bad request, auth, etc. — no point retrying.
                raise
            last_error = exc
        except requests.RequestException as exc:
            last_error = exc

        if attempt < max_attempts:
            backoff = base_backoff * (2 ** (attempt - 1))
            logger.warning(
                "POST attempt %s/%s failed (%s); retrying in %.1fs.",
                attempt,
                max_attempts,
                last_error,
                backoff,
            )
            sleep(backoff)

    assert last_error is not None
    raise last_error


def _run_once(
    *,
    api_url: str,
    start: datetime,
    end: datetime,
    state: dict[str, Any] | None = None,
    dry_run: bool = False,
    max_retries: int = 5,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Pull deals in [start, end], filter, and (unless dry-run) POST.

    Returns ``(new_records, server_response)`` where ``server_response`` is
    ``None`` for a no-op tick or dry run.
    """
    logger.info("Fetching deals from %s → %s.", start.isoformat(), end.isoformat())
    records = _build_trade_records(start, end)
    last_seen = (state or {}).get("last_seen_close_time")
    new_records = _filter_new_records(records, last_seen)

    if not new_records:
        logger.info(
            "No new trades to upload (%s candidate deal aggregates).", len(records)
        )
        return [], None

    if dry_run:
        logger.info("[dry-run] Would POST %s record(s).", len(new_records))
        print(json.dumps(new_records, indent=2)[:4000])
        return new_records, None

    response = _post_with_retry(api_url, new_records, max_attempts=max_retries)
    logger.info("Server: %s", response)
    return new_records, response


def _watch_loop(
    args: argparse.Namespace,
    *,
    sleep: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    stop_after_iterations: int | None = None,
) -> None:
    """Run the polling loop until SIGINT/SIGTERM (or `stop_after_iterations`).

    `sleep` and `now_fn` are dependency-injected so unit tests can drive the
    loop deterministically without real time passing.
    """
    state = _load_state(args.state_file)
    logger.info(
        "Watching MT5 every %ss; state file=%s; last seen=%s",
        args.interval,
        args.state_file,
        state.get("last_seen_close_time", "never"),
    )

    stop_flag = {"stop": False}

    def _request_stop(*_: Any) -> None:
        logger.info("Stop signal received; finishing current tick and exiting.")
        stop_flag["stop"] = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _request_stop)
        except (
            ValueError,
            OSError,
        ):  # pragma: no cover — non-main thread or unsupported signal
            pass

    iteration = 0
    while not stop_flag["stop"]:
        iteration += 1
        end = now_fn()
        last_seen = state.get("last_seen_close_time")
        if last_seen:
            try:
                start = datetime.fromisoformat(last_seen) - timedelta(
                    seconds=WATCH_BACKFILL_SECONDS
                )
            except ValueError:
                start = end - timedelta(days=args.days)
        else:
            start = end - timedelta(days=args.days)

        try:
            new_records, _ = _run_once(
                api_url=args.api_url,
                start=start,
                end=end,
                state=state,
                dry_run=args.dry_run,
                max_retries=args.max_retries,
            )
            highwater = _records_highwater(new_records)
            if highwater:
                state["last_seen_close_time"] = highwater
            state["last_run_at"] = end.isoformat()
            _save_state(args.state_file, state)
        except requests.RequestException as exc:
            logger.error("Tick failed (network): %s", exc)
        except Exception as exc:  # noqa: BLE001 — we want to keep the loop alive
            logger.exception("Tick failed (unexpected): %s", exc)

        if stop_after_iterations is not None and iteration >= stop_after_iterations:
            break

        if not stop_flag["stop"]:
            sleep(args.interval)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _initialize_mt5(args)

    if args.watch:
        _watch_loop(args)
        return

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)
    _run_once(
        api_url=args.api_url,
        start=start,
        end=end,
        dry_run=args.dry_run,
        max_retries=args.max_retries,
    )


if __name__ == "__main__":
    main()
