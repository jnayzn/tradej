"""Tests for the trades app."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from . import analytics, importers
from .models import Trade

User = get_user_model()


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
    user=None,
) -> Trade:
    base = open_time or datetime(2024, 5, 1, 9, 0, tzinfo=UTC)
    return Trade.objects.create(
        user=user,
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
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="alice", password="alice12345!")

    def test_csv_round_trip(self) -> None:
        csv = (
            "Ticket,Symbol,Type,Volume,Open Time,Close Time,Open Price,Close Price,Profit\n"
            "1001,EURUSD,buy,0.10,2024.05.01 09:00:00,2024.05.01 09:30:00,1.1000,1.1010,10\n"
            "1002,XAUUSD,SELL,0.05,2024.05.01 10:00:00,2024.05.01 10:45:00,2300.5,2299.0,7.5\n"
        )
        records = importers.parse_csv(csv)
        result = importers.import_records(records, user=self.user)
        self.assertEqual(result.created, 2)
        self.assertEqual(Trade.objects.count(), 2)
        eu = Trade.objects.get(user=self.user, ticket=1001)
        self.assertEqual(eu.symbol, "EURUSD")
        self.assertEqual(eu.order_type, Trade.OrderType.BUY)

    def test_csv_dedupes_by_ticket(self) -> None:
        csv = (
            "Ticket,Symbol,Type,Volume,Open Time,Close Time,Open Price,Close Price,Profit\n"
            "1001,EURUSD,buy,0.10,2024.05.01 09:00:00,2024.05.01 09:30:00,1.1,1.11,10\n"
        )
        importers.import_records(importers.parse_csv(csv), user=self.user)
        # Re-import the same row but with a different profit -> should update, not duplicate.
        csv2 = csv.replace(",10\n", ",42\n")
        result = importers.import_records(importers.parse_csv(csv2), user=self.user)
        self.assertEqual(result.created, 0)
        self.assertEqual(result.updated, 1)
        self.assertEqual(Trade.objects.count(), 1)
        self.assertEqual(Trade.objects.get(user=self.user, ticket=1001).profit, Decimal("42"))

    def test_same_ticket_under_two_users_is_not_a_conflict(self) -> None:
        """Two users may legitimately have a trade with the same ticket
        (e.g. on different brokers). The unique constraint must scope by
        (user, ticket), not by ticket alone."""
        bob = User.objects.create_user(username="bob", password="bobpass1234!")
        csv = (
            "Ticket,Symbol,Type,Volume,Open Time,Close Time,Open Price,Close Price,Profit\n"
            "1001,EURUSD,buy,0.10,2024.05.01 09:00:00,2024.05.01 09:30:00,1.1,1.11,10\n"
        )
        importers.import_records(importers.parse_csv(csv), user=self.user)
        importers.import_records(importers.parse_csv(csv), user=bob)
        self.assertEqual(Trade.objects.count(), 2)
        self.assertEqual(Trade.objects.filter(user=self.user, ticket=1001).count(), 1)
        self.assertEqual(Trade.objects.filter(user=bob, ticket=1001).count(), 1)

    def test_json_array(self) -> None:
        payload = (
            '[{"ticket":2001,"symbol":"BTCUSD","type":"buy","volume":0.01,'
            '"open_time":"2024-05-01T09:00:00Z","close_time":"2024-05-01T10:00:00Z",'
            '"profit":15}]'
        )
        records = importers.parse_json(payload)
        result = importers.import_records(records, user=self.user)
        self.assertEqual(result.created, 1)

    def test_api_export_round_trips(self) -> None:
        """The serializer emits `order_type` (the model field), so a JSON
        export from /api/trades/ must be re-importable as-is.
        """
        payload = (
            '[{"ticket":3001,"symbol":"EURUSD","order_type":"SELL","volume":0.20,'
            '"open_time":"2024-05-01T09:00:00Z","close_time":"2024-05-01T10:00:00Z",'
            '"open_price":1.1,"close_price":1.09,"profit":20}]'
        )
        records = importers.parse_json(payload)
        result = importers.import_records(records, user=self.user)
        self.assertEqual(result.created, 1, result.errors)
        t = Trade.objects.get(user=self.user, ticket=3001)
        self.assertEqual(t.order_type, Trade.OrderType.SELL)


class APITests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="trader", password="trader1234!")
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        base = datetime(2024, 5, 1, 9, 0, tzinfo=UTC)
        for i, p in enumerate([100, -50, 30]):
            make_trade(
                profit=str(p),
                open_time=base + timedelta(days=i),
                close_time=base + timedelta(days=i, minutes=30),
                user=self.user,
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
        self.assertEqual(Trade.objects.get(ticket=9001).user, self.user)


class APIAuthRequiredTests(TestCase):
    """Anonymous requests must be rejected on every protected endpoint."""

    def setUp(self) -> None:
        self.client = APIClient()  # no credentials

    def test_list_trades_unauthenticated(self) -> None:
        resp = self.client.get(reverse("trade-list"))
        self.assertIn(resp.status_code, (401, 403))

    def test_summary_unauthenticated(self) -> None:
        resp = self.client.get(reverse("stats-summary"))
        self.assertIn(resp.status_code, (401, 403))

    def test_import_unauthenticated(self) -> None:
        resp = self.client.post(reverse("trade-import-trades"), data={"csv": ""})
        self.assertIn(resp.status_code, (401, 403))


class MultiUserIsolationTests(TestCase):
    """Two users must never see each other's trades through any endpoint."""

    def setUp(self) -> None:
        self.alice = User.objects.create_user(username="alice", password="alicepw1234!")
        self.bob = User.objects.create_user(username="bob", password="bobpw1234!")
        self.alice_token = Token.objects.create(user=self.alice)
        self.bob_token = Token.objects.create(user=self.bob)
        # Alice has 2 trades, Bob has 1.
        make_trade(profit="100", user=self.alice, ticket=1)
        make_trade(profit="50", user=self.alice, ticket=2)
        make_trade(profit="-20", user=self.bob, ticket=3)

    def _client_for(self, token: Token) -> APIClient:
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return c

    def test_list_trades_only_returns_own(self) -> None:
        alice = self._client_for(self.alice_token)
        bob = self._client_for(self.bob_token)
        self.assertEqual(alice.get(reverse("trade-list")).json()["count"], 2)
        self.assertEqual(bob.get(reverse("trade-list")).json()["count"], 1)

    def test_summary_is_per_user(self) -> None:
        alice = self._client_for(self.alice_token)
        bob = self._client_for(self.bob_token)
        self.assertAlmostEqual(alice.get(reverse("stats-summary")).json()["total_pnl"], 150.0)
        self.assertAlmostEqual(bob.get(reverse("stats-summary")).json()["total_pnl"], -20.0)

    def test_cannot_fetch_other_users_trade_by_id(self) -> None:
        alice_trade = Trade.objects.get(user=self.alice, ticket=1)
        bob = self._client_for(self.bob_token)
        resp = bob.get(reverse("trade-detail", args=[alice_trade.id]))
        self.assertEqual(resp.status_code, 404)


class AuthEndpointsTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()

    def test_register_creates_user_and_returns_token(self) -> None:
        resp = self.client.post(
            reverse("auth-register"),
            data={"username": "newbie", "email": "n@x.com", "password": "Sup3rs3cret!"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertEqual(body["user"]["username"], "newbie")
        self.assertEqual(body["user"]["email"], "n@x.com")
        self.assertTrue(body["token"])
        self.assertTrue(User.objects.filter(username="newbie").exists())

    def test_register_rejects_duplicate_username_case_insensitive(self) -> None:
        User.objects.create_user(username="dup", password="whatever1234!")
        resp = self.client.post(
            reverse("auth-register"),
            data={"username": "DUP", "password": "Sup3rs3cret!"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_register_rejects_short_password(self) -> None:
        resp = self.client.post(
            reverse("auth-register"),
            data={"username": "shorty", "password": "1234"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_register_returns_400_on_concurrent_duplicate_username(self) -> None:
        # Simulates the TOCTOU race: ``validate_username`` says the name is
        # free, but a sibling request beats us to ``create_user`` and the DB
        # unique constraint fires. Without the IntegrityError handler this
        # surfaces as a 500.
        with mock.patch(
            "trades.auth_views.User.objects.create_user",
            side_effect=IntegrityError("UNIQUE constraint failed"),
        ):
            resp = self.client.post(
                reverse("auth-register"),
                data={"username": "racer", "password": "Sup3rs3cret!"},
                format="json",
            )
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn("username", resp.json())

    def test_register_rejects_password_too_similar_to_username(self) -> None:
        # Engages Django's UserAttributeSimilarityValidator — only effective
        # when the candidate user is passed to validate_password().
        resp = self.client.post(
            reverse("auth-register"),
            data={"username": "traderking", "password": "traderking1"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.content)
        body = resp.json()
        self.assertIn("password", body)

    def test_login_returns_token(self) -> None:
        User.objects.create_user(username="loginer", password="LoginPass1!")
        resp = self.client.post(
            reverse("auth-login"),
            data={"username": "loginer", "password": "LoginPass1!"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()["token"])

    def test_login_rejects_bad_password(self) -> None:
        User.objects.create_user(username="loginer2", password="LoginPass1!")
        resp = self.client.post(
            reverse("auth-login"),
            data={"username": "loginer2", "password": "wrong"},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_me_returns_user_when_authenticated(self) -> None:
        u = User.objects.create_user(username="me", password="MePassword1!")
        token = Token.objects.create(user=u)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        resp = self.client.get(reverse("auth-me"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["user"]["username"], "me")
        self.assertEqual(resp.json()["token"], token.key)

    def test_me_requires_auth(self) -> None:
        resp = self.client.get(reverse("auth-me"))
        self.assertIn(resp.status_code, (401, 403))

    def test_regenerate_token_replaces_old_one(self) -> None:
        u = User.objects.create_user(username="rotater", password="RotPass12345!")
        old = Token.objects.create(user=u)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {old.key}")
        resp = self.client.post(reverse("auth-regenerate-token"))
        self.assertEqual(resp.status_code, 200)
        new_key = resp.json()["token"]
        self.assertNotEqual(new_key, old.key)
        # Old token must no longer work.
        self.assertFalse(Token.objects.filter(key=old.key).exists())
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {old.key}")
        self.assertIn(self.client.get(reverse("auth-me")).status_code, (401, 403))
