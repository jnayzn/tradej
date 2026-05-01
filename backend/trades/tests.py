"""Tests for the trades app."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from . import analytics, importers
from .models import Trade


def make_trade(
    symbol: str = "EURUSD",
    order_type: str = Trade.OrderType.BUY,
    profit: str | Decimal = "10",
    *,
    open_time: datetime | None = None,
    close_time: datetime | None = None,
    volume: str | Decimal = "0.10",
    ticket: int | None = None,
    commission: str | Decimal = "0",
    swap: str | Decimal = "0",
) -> Trade:
    base = open_time or datetime(2024, 5, 1, 9, 0, tzinfo=UTC)
    return Trade.objects.create(
        ticket=ticket,
        symbol=symbol,
        order_type=order_type,
        volume=Decimal(str(volume)),
        open_time=base,
        close_time=close_time or (base + timedelta(minutes=30)),
        open_price=Decimal("1.10"),
        close_price=Decimal("1.11"),
        profit=Decimal(str(profit)),
        commission=Decimal(str(commission)),
        swap=Decimal(str(swap)),
    )


class TradeModelTests(TestCase):
    def test_net_profit_includes_swap_and_commission(self) -> None:
        t = make_trade(profit="100", commission="-3", swap="-1")
        self.assertEqual(t.net_profit, Decimal("96"))
        self.assertTrue(t.is_win)


class AnalyticsTests(TestCase):
    def setUp(self) -> None:
        # Build a small but realistic ledger.
        # Trades: +100, -50, +30, -20, +0
        base = datetime(2024, 5, 1, 9, 0, tzinfo=UTC)
        for i, p in enumerate([100, -50, 30, -20, 0]):
            make_trade(
                profit=str(p),
                open_time=base + timedelta(days=i),
                close_time=base + timedelta(days=i, minutes=30),
            )

    def test_summary_basic_metrics(self) -> None:
        s = analytics.summary(Trade.objects.all())
        self.assertEqual(s["total_trades"], 5)
        self.assertEqual(s["wins"], 2)
        self.assertEqual(s["losses"], 2)
        self.assertEqual(s["breakeven"], 1)
        self.assertAlmostEqual(s["winrate"], 40.0)
        self.assertAlmostEqual(s["total_pnl"], 60.0)
        self.assertAlmostEqual(s["gross_profit"], 130.0)
        self.assertAlmostEqual(s["gross_loss"], -70.0)
        self.assertAlmostEqual(s["biggest_win"], 100.0)
        self.assertAlmostEqual(s["biggest_loss"], -50.0)
        self.assertAlmostEqual(s["average_win"], 65.0)
        self.assertAlmostEqual(s["average_loss"], -35.0)
        self.assertAlmostEqual(s["profit_factor"], round(130 / 70, 2))

    def test_equity_curve_is_monotonic_with_trades(self) -> None:
        points = analytics.equity_curve(Trade.objects.all())
        self.assertEqual(len(points), 5)
        equities = [p["equity"] for p in points]
        self.assertEqual(equities[-1], 60.0)
        self.assertEqual(equities[0], 100.0)

    def test_calendar_groups_by_day(self) -> None:
        result = analytics.calendar_view(Trade.objects.all(), 2024, 5)
        non_zero = [d for d in result["days"] if d["trades"] > 0]
        self.assertEqual(len(non_zero), 5)
        self.assertEqual(sum(d["pnl"] for d in non_zero), 60.0)


class InsightsTests(TestCase):
    def test_revenge_trade_is_flagged(self) -> None:
        base = datetime(2024, 5, 1, 9, 0, tzinfo=UTC)
        # Loss, then a much-bigger same-symbol entry within 5 minutes -> revenge.
        loss = make_trade(
            symbol="EURUSD",
            profit="-50",
            open_time=base,
            close_time=base + timedelta(minutes=10),
            volume="0.10",
        )
        make_trade(
            symbol="EURUSD",
            profit="20",
            open_time=loss.close_time + timedelta(minutes=5),
            close_time=loss.close_time + timedelta(minutes=20),
            volume="0.30",
        )
        result = analytics.insights(Trade.objects.all())
        self.assertGreaterEqual(result["metrics"]["revenge_trades"], 1)
        kinds = {f["kind"] for f in result["findings"]}
        self.assertIn("danger", kinds)

    def test_overtrading_is_flagged(self) -> None:
        base = datetime(2024, 5, 1, 9, 0, tzinfo=UTC)
        for i in range(analytics.OVERTRADE_DAILY_THRESHOLD + 2):
            make_trade(
                symbol="EURUSD",
                profit="1",
                open_time=base + timedelta(minutes=i * 5),
                close_time=base + timedelta(minutes=i * 5 + 1),
            )
        result = analytics.insights(Trade.objects.all())
        self.assertGreaterEqual(result["metrics"]["overtrade_days"], 1)


class ImportersTests(TestCase):
    def test_csv_round_trip(self) -> None:
        csv = (
            "Ticket,Symbol,Type,Volume,Open Time,Close Time,Open Price,Close Price,Profit\n"
            "1001,EURUSD,buy,0.10,2024.05.01 09:00:00,2024.05.01 09:30:00,1.1000,1.1010,10\n"
            "1002,XAUUSD,SELL,0.05,2024.05.01 10:00:00,2024.05.01 10:45:00,2300.5,2299.0,7.5\n"
        )
        records = importers.parse_csv(csv)
        result = importers.import_records(records)
        self.assertEqual(result.created, 2)
        self.assertEqual(Trade.objects.count(), 2)
        eu = Trade.objects.get(ticket=1001)
        self.assertEqual(eu.symbol, "EURUSD")
        self.assertEqual(eu.order_type, Trade.OrderType.BUY)

    def test_csv_dedupes_by_ticket(self) -> None:
        csv = (
            "Ticket,Symbol,Type,Volume,Open Time,Close Time,Open Price,Close Price,Profit\n"
            "1001,EURUSD,buy,0.10,2024.05.01 09:00:00,2024.05.01 09:30:00,1.1,1.11,10\n"
        )
        importers.import_records(importers.parse_csv(csv))
        # Re-import the same row but with a different profit -> should update, not duplicate.
        csv2 = csv.replace(",10\n", ",42\n")
        result = importers.import_records(importers.parse_csv(csv2))
        self.assertEqual(result.created, 0)
        self.assertEqual(result.updated, 1)
        self.assertEqual(Trade.objects.count(), 1)
        self.assertEqual(Trade.objects.get(ticket=1001).profit, Decimal("42"))

    def test_json_array(self) -> None:
        payload = (
            '[{"ticket":2001,"symbol":"BTCUSD","type":"buy","volume":0.01,'
            '"open_time":"2024-05-01T09:00:00Z","close_time":"2024-05-01T10:00:00Z",'
            '"profit":15}]'
        )
        records = importers.parse_json(payload)
        result = importers.import_records(records)
        self.assertEqual(result.created, 1)


class APITests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        base = datetime(2024, 5, 1, 9, 0, tzinfo=UTC)
        for i, p in enumerate([100, -50, 30]):
            make_trade(
                profit=str(p),
                open_time=base + timedelta(days=i),
                close_time=base + timedelta(days=i, minutes=30),
            )

    def test_list_trades(self) -> None:
        resp = self.client.get(reverse("trade-list"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 3)

    def test_summary_endpoint(self) -> None:
        resp = self.client.get(reverse("stats-summary"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["total_trades"], 3)
        self.assertAlmostEqual(resp.json()["total_pnl"], 80.0)

    def test_equity_endpoint(self) -> None:
        resp = self.client.get(reverse("stats-equity"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["points"]), 3)

    def test_calendar_endpoint(self) -> None:
        resp = self.client.get(reverse("stats-calendar"), {"year": 2024, "month": 5})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["year"], 2024)

    def test_insights_endpoint(self) -> None:
        resp = self.client.get(reverse("stats-insights"))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("score", body)
        self.assertIn("findings", body)
        self.assertIn("metrics", body)

    def test_import_csv_endpoint(self) -> None:
        csv = (
            "Ticket,Symbol,Type,Volume,Open Time,Close Time,Open Price,Close Price,Profit\n"
            "9001,EURUSD,buy,0.10,2024.05.01 09:00:00,2024.05.01 09:30:00,1.1,1.11,12\n"
        )
        resp = self.client.post(
            reverse("trade-import-trades"),
            data={"csv": csv},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["created"], 1)
