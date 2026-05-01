"""Unit tests for the MT5 bridge.

These tests exercise pure-Python helpers in `mt5_bridge.py` without the
Windows-only `MetaTrader5` package; that dependency is optional and the module
falls back to `mt5 = None` when missing.

Run from the `bridge/` directory::

    python -m unittest test_mt5_bridge
"""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import requests

import mt5_bridge
from mt5_bridge import (
    DEAL_TYPE_BUY,
    DEAL_TYPE_SELL,
    _advance_highwater,
    _filter_new_records,
    _load_state,
    _position_order_type,
    _post_with_retry,
    _records_highwater,
    _save_state,
    _watch_loop,
)


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


class FilterNewRecordsTests(unittest.TestCase):
    records = [
        {"ticket": 1, "close_time": "2024-05-01T09:00:00+00:00"},
        {"ticket": 2, "close_time": "2024-05-01T10:00:00+00:00"},
        {"ticket": 3, "close_time": "2024-05-01T11:00:00+00:00"},
    ]

    def test_returns_all_records_when_no_highwater(self) -> None:
        self.assertEqual(_filter_new_records(self.records, None), self.records)
        self.assertEqual(_filter_new_records(self.records, ""), self.records)

    def test_drops_strictly_older_records(self) -> None:
        # Without a seen-set, equal-to-highwater is *kept* (otherwise the
        # backfill window can't catch boundary-second siblings) but strictly
        # older records are still dropped.
        result = _filter_new_records(self.records, "2024-05-01T10:00:00+00:00")
        self.assertEqual([r["ticket"] for r in result], [2, 3])

    def test_drops_records_already_seen_at_highwater(self) -> None:
        # When the highwater ticket(s) are recorded, the sibling at the
        # boundary is what's left.
        result = _filter_new_records(
            self.records,
            "2024-05-01T10:00:00+00:00",
            seen_tickets_at_highwater=[2],
        )
        self.assertEqual([r["ticket"] for r in result], [3])

    def test_drops_all_when_highwater_after_everything(self) -> None:
        result = _filter_new_records(
            self.records,
            "2024-05-01T12:00:00+00:00",
            seen_tickets_at_highwater=[1, 2, 3],
        )
        self.assertEqual(result, [])

    def test_boundary_sibling_is_picked_up_on_next_tick(self) -> None:
        """Regression test for the WATCH_BACKFILL_SECONDS / strict-> bug.

        Two trades A and B both close at exactly 10:00:00 UTC. On tick 1 MT5
        only returns A (B has not settled yet). The highwater advances to
        10:00:00 with seen={A}. On tick 2 MT5 returns both A and B. We must
        keep B (the new sibling) and drop A (the one we already POSTed).
        """
        boundary = "2024-05-01T10:00:00+00:00"
        a = {"ticket": "A", "close_time": boundary}
        b = {"ticket": "B", "close_time": boundary}

        # Tick 1 — only A is visible.
        first = _filter_new_records([a], None)
        self.assertEqual(first, [a])

        # State after tick 1.
        state: dict[str, Any] = {}
        _advance_highwater(state, first)
        self.assertEqual(state["last_seen_close_time"], boundary)
        self.assertEqual(state["seen_tickets_at_highwater"], ["A"])

        # Tick 2 — MT5 now returns both because of the 60s backfill window.
        second = _filter_new_records(
            [a, b],
            state["last_seen_close_time"],
            state["seen_tickets_at_highwater"],
        )
        self.assertEqual(second, [b], "the boundary-second sibling B must be POSTed")

        # State after tick 2 — highwater unchanged, both tickets remembered.
        _advance_highwater(state, second)
        self.assertEqual(state["last_seen_close_time"], boundary)
        self.assertEqual(state["seen_tickets_at_highwater"], ["A", "B"])

        # Tick 3 — MT5 still returns A and B; both must now be filtered.
        third = _filter_new_records(
            [a, b],
            state["last_seen_close_time"],
            state["seen_tickets_at_highwater"],
        )
        self.assertEqual(third, [])


class AdvanceHighwaterTests(unittest.TestCase):
    def test_no_op_when_no_records(self) -> None:
        state: dict[str, Any] = {
            "last_seen_close_time": "2024-05-01T10:00:00+00:00",
            "seen_tickets_at_highwater": [1],
        }
        _advance_highwater(state, [])
        self.assertEqual(state["last_seen_close_time"], "2024-05-01T10:00:00+00:00")
        self.assertEqual(state["seen_tickets_at_highwater"], [1])

    def test_advance_replaces_seen_tickets_when_highwater_grows(self) -> None:
        state: dict[str, Any] = {
            "last_seen_close_time": "2024-05-01T10:00:00+00:00",
            "seen_tickets_at_highwater": ["A"],
        }
        _advance_highwater(
            state,
            [
                {"ticket": "C", "close_time": "2024-05-01T10:30:00+00:00"},
                {"ticket": "D", "close_time": "2024-05-01T10:30:00+00:00"},
            ],
        )
        self.assertEqual(state["last_seen_close_time"], "2024-05-01T10:30:00+00:00")
        # Old ["A"] is wiped because the highwater moved past 10:00:00.
        self.assertEqual(state["seen_tickets_at_highwater"], ["C", "D"])

    def test_advance_unions_when_highwater_unchanged(self) -> None:
        state: dict[str, Any] = {
            "last_seen_close_time": "2024-05-01T10:00:00+00:00",
            "seen_tickets_at_highwater": ["A"],
        }
        _advance_highwater(
            state,
            [{"ticket": "B", "close_time": "2024-05-01T10:00:00+00:00"}],
        )
        self.assertEqual(state["last_seen_close_time"], "2024-05-01T10:00:00+00:00")
        self.assertEqual(state["seen_tickets_at_highwater"], ["A", "B"])

    def test_advance_ignores_records_with_no_ticket(self) -> None:
        state: dict[str, Any] = {}
        _advance_highwater(
            state,
            [{"close_time": "2024-05-01T10:00:00+00:00"}],
        )
        # Highwater still advances; ticket list stays empty.
        self.assertEqual(state["last_seen_close_time"], "2024-05-01T10:00:00+00:00")
        self.assertEqual(state["seen_tickets_at_highwater"], [])


class HighwaterTests(unittest.TestCase):
    def test_returns_max_close_time(self) -> None:
        records = [
            {"close_time": "2024-05-01T09:00:00+00:00"},
            {"close_time": "2024-05-01T11:00:00+00:00"},
            {"close_time": "2024-05-01T10:00:00+00:00"},
        ]
        self.assertEqual(_records_highwater(records), "2024-05-01T11:00:00+00:00")

    def test_returns_none_for_empty(self) -> None:
        self.assertIsNone(_records_highwater([]))

    def test_ignores_records_without_close_time(self) -> None:
        records = [{"close_time": "2024-05-01T09:00:00+00:00"}, {"ticket": 2}]
        self.assertEqual(_records_highwater(records), "2024-05-01T09:00:00+00:00")


class StateRoundTripTests(unittest.TestCase):
    def test_load_returns_empty_when_file_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.json"
            self.assertEqual(_load_state(path), {})

    def test_save_then_load_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = {"last_seen_close_time": "2024-05-01T11:00:00+00:00"}
            _save_state(path, state)
            self.assertEqual(_load_state(path), state)
            # No leftover .tmp file from the atomic write.
            self.assertFalse(path.with_suffix(path.suffix + ".tmp").exists())

    def test_load_handles_corrupt_state_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("{not valid json")
            # Corrupt content -> empty state, daemon stays alive.
            self.assertEqual(_load_state(path), {})

    def test_save_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "dirs" / "state.json"
            _save_state(path, {"k": "v"})
            self.assertEqual(_load_state(path), {"k": "v"})


class _MockResponse:
    def __init__(
        self, *, status_code: int = 200, payload: dict[str, Any] | None = None
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {"ok": True}

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if 400 <= self.status_code:
            err = requests.HTTPError(f"HTTP {self.status_code}")
            err.response = self  # type: ignore[assignment]
            raise err


class PostWithRetryTests(unittest.TestCase):
    def test_succeeds_first_try(self) -> None:
        sleeps: list[float] = []
        with mock.patch(
            "mt5_bridge.requests.post", return_value=_MockResponse()
        ) as post:
            result = _post_with_retry(
                "http://example/api",
                [{"ticket": 1}],
                sleep=sleeps.append,
            )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(post.call_count, 1)
        self.assertEqual(sleeps, [])

    def test_retries_on_transient_network_error_then_succeeds(self) -> None:
        sleeps: list[float] = []
        responses = [
            requests.ConnectionError("DNS lookup failed"),
            requests.ConnectionError("connection reset"),
            _MockResponse(payload={"created": 1}),
        ]

        def _post(*_args: Any, **_kwargs: Any) -> _MockResponse:
            r = responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        with mock.patch("mt5_bridge.requests.post", side_effect=_post):
            result = _post_with_retry(
                "http://example/api",
                [{"ticket": 1}],
                base_backoff=2.0,
                sleep=sleeps.append,
            )
        self.assertEqual(result, {"created": 1})
        # 2 retries → 2 backoff sleeps (2s, 4s).
        self.assertEqual(sleeps, [2.0, 4.0])

    def test_does_not_retry_4xx(self) -> None:
        sleeps: list[float] = []
        with mock.patch(
            "mt5_bridge.requests.post",
            return_value=_MockResponse(status_code=400, payload={"error": "bad"}),
        ) as post:
            with self.assertRaises(requests.HTTPError):
                _post_with_retry(
                    "http://example/api",
                    [{"ticket": 1}],
                    sleep=sleeps.append,
                )
        self.assertEqual(post.call_count, 1, "4xx should not be retried")
        self.assertEqual(sleeps, [])

    def test_gives_up_after_max_attempts(self) -> None:
        sleeps: list[float] = []
        with mock.patch(
            "mt5_bridge.requests.post",
            side_effect=requests.ConnectionError("nope"),
        ) as post:
            with self.assertRaises(requests.ConnectionError):
                _post_with_retry(
                    "http://example/api",
                    [{"ticket": 1}],
                    max_attempts=3,
                    base_backoff=1.0,
                    sleep=sleeps.append,
                )
        self.assertEqual(post.call_count, 3)
        # 2 inter-attempt sleeps before the final failure (no sleep after last try).
        self.assertEqual(sleeps, [1.0, 2.0])


class WatchLoopTests(unittest.TestCase):
    def _args(self, state_file: Path, **overrides: Any) -> argparse.Namespace:
        defaults = {
            "api_url": "http://example/api",
            "days": 30,
            "login": None,
            "password": None,
            "server": None,
            "terminal_path": None,
            "dry_run": False,
            "watch": True,
            "interval": 1,
            "state_file": state_file,
            "max_retries": 3,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_loop_runs_tick_and_persists_highwater(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "state.json"
            args = self._args(state_file)

            new_records = [{"ticket": 42, "close_time": "2024-05-01T11:00:00+00:00"}]
            sleeps: list[float] = []
            with (
                mock.patch.object(
                    mt5_bridge,
                    "_run_once",
                    return_value=(new_records, {"created": 1}),
                ) as run_once,
                mock.patch.object(
                    mt5_bridge.signal,
                    "signal",
                ),  # don't actually install handlers in tests
            ):
                _watch_loop(args, sleep=sleeps.append, stop_after_iterations=1)

            run_once.assert_called_once()
            persisted = _load_state(state_file)
            self.assertEqual(
                persisted.get("last_seen_close_time"),
                "2024-05-01T11:00:00+00:00",
            )
            # The watch loop must persist the boundary-tickets set so the
            # next tick can distinguish a duplicate from a sibling.
            self.assertEqual(persisted.get("seen_tickets_at_highwater"), [42])
            self.assertIn("last_run_at", persisted)
            # Sleep was called between iterations — but with only 1 iteration
            # AND stop_after_iterations triggering the break before the sleep
            # path. Either way, no sleep > 0 is expected when we stop after 1.
            self.assertEqual(sleeps, [])

    def test_loop_keeps_running_when_tick_raises(self) -> None:
        """A network error inside _run_once must not crash the loop."""
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "state.json"
            args = self._args(state_file)
            sleeps: list[float] = []

            calls = {"n": 0}

            def _flaky(
                **_kwargs: Any,
            ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
                calls["n"] += 1
                if calls["n"] == 1:
                    raise requests.ConnectionError("boom")
                return (
                    [{"ticket": 7, "close_time": "2024-05-02T00:00:00+00:00"}],
                    {"created": 1},
                )

            with (
                mock.patch.object(mt5_bridge, "_run_once", side_effect=_flaky),
                mock.patch.object(mt5_bridge.signal, "signal"),
            ):
                _watch_loop(args, sleep=sleeps.append, stop_after_iterations=2)

            self.assertEqual(calls["n"], 2)
            persisted = _load_state(state_file)
            # Highwater advances after the successful 2nd tick.
            self.assertEqual(
                persisted.get("last_seen_close_time"),
                "2024-05-02T00:00:00+00:00",
            )
            # One sleep between the 2 iterations (interval=1).
            self.assertEqual(sleeps, [1])


if __name__ == "__main__":
    unittest.main()
