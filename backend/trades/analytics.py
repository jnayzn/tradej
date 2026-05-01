"""Aggregate analytics over the Trade table.

Everything here operates on a queryset of :class:`Trade` so it can be reused by
both endpoints and tests, and so it stays cheap on small / medium datasets.
"""

from __future__ import annotations

import calendar as _calendar
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet

from .models import Trade

ZERO = Decimal("0")


def _net(t: Trade) -> Decimal:
    return (t.profit or ZERO) + (t.commission or ZERO) + (t.swap or ZERO)


def _to_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def summary(qs: QuerySet[Trade]) -> dict[str, Any]:
    """Headline stats: PnL, winrate, biggest/avg win/loss, profit factor, expectancy."""
    trades = list(qs.order_by("close_time"))
    total = len(trades)
    if total == 0:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "breakeven": 0,
            "winrate": 0.0,
            "total_pnl": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "biggest_win": 0.0,
            "biggest_loss": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "average_trade": 0.0,
        }

    wins: list[Decimal] = []
    losses: list[Decimal] = []
    breakeven = 0
    total_pnl = ZERO
    for t in trades:
        n = _net(t)
        total_pnl += n
        if n > 0:
            wins.append(n)
        elif n < 0:
            losses.append(n)
        else:
            breakeven += 1

    gross_profit = sum(wins, ZERO)
    gross_loss = sum(losses, ZERO)  # negative
    biggest_win = max(wins) if wins else ZERO
    biggest_loss = min(losses) if losses else ZERO
    avg_win = (gross_profit / len(wins)) if wins else ZERO
    avg_loss = (gross_loss / len(losses)) if losses else ZERO
    winrate = (len(wins) / total) * 100 if total else 0
    profit_factor = (
        float(gross_profit / abs(gross_loss))
        if gross_loss != 0
        else float("inf")
        if gross_profit > 0
        else 0.0
    )
    # Cap profit_factor for JSON serialization sanity.
    if profit_factor == float("inf"):
        profit_factor = 999.0
    expectancy = (winrate / 100) * float(avg_win) + (1 - winrate / 100) * float(avg_loss)

    return {
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": breakeven,
        "winrate": round(winrate, 2),
        "total_pnl": _to_float(total_pnl),
        "gross_profit": _to_float(gross_profit),
        "gross_loss": _to_float(gross_loss),
        "biggest_win": _to_float(biggest_win),
        "biggest_loss": _to_float(biggest_loss),
        "average_win": _to_float(avg_win),
        "average_loss": _to_float(avg_loss),
        "profit_factor": round(profit_factor, 2),
        "expectancy": round(expectancy, 2),
        "average_trade": _to_float(total_pnl / total) if total else 0.0,
    }


def equity_curve(qs: QuerySet[Trade]) -> list[dict[str, Any]]:
    """Cumulative net PnL after each closed trade, in chronological order."""
    trades = list(qs.order_by("close_time", "id"))
    out: list[dict[str, Any]] = []
    running = ZERO
    for t in trades:
        running += _net(t)
        out.append(
            {
                "trade_id": t.id,
                "close_time": t.close_time.isoformat(),
                "symbol": t.symbol,
                "pnl": _to_float(_net(t)),
                "equity": _to_float(running),
            }
        )
    return out


def calendar_view(qs: QuerySet[Trade], year: int, month: int) -> dict[str, Any]:
    """Per-day stats for one month: net PnL and trade count."""
    start = datetime(year, month, 1, tzinfo=UTC)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(year, month + 1, 1, tzinfo=UTC)

    by_day: dict[date, dict[str, Any]] = defaultdict(
        lambda: {"pnl": ZERO, "trades": 0, "wins": 0, "losses": 0}
    )
    for t in qs.filter(close_time__gte=start, close_time__lt=end):
        day = t.close_time.date()
        bucket = by_day[day]
        bucket["pnl"] += _net(t)
        bucket["trades"] += 1
        if _net(t) > 0:
            bucket["wins"] += 1
        elif _net(t) < 0:
            bucket["losses"] += 1

    days = []
    n_days = _calendar.monthrange(year, month)[1]
    for d in range(1, n_days + 1):
        the_date = date(year, month, d)
        bucket = by_day.get(the_date)
        if bucket:
            days.append(
                {
                    "date": the_date.isoformat(),
                    "pnl": _to_float(bucket["pnl"]),
                    "trades": bucket["trades"],
                    "wins": bucket["wins"],
                    "losses": bucket["losses"],
                }
            )
        else:
            days.append(
                {
                    "date": the_date.isoformat(),
                    "pnl": 0.0,
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                }
            )
    return {"year": year, "month": month, "days": days}


def by_symbol(qs: QuerySet[Trade]) -> list[dict[str, Any]]:
    """Per-symbol aggregates."""
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"trades": 0, "wins": 0, "losses": 0, "pnl": ZERO}
    )
    for t in qs:
        b = buckets[t.symbol]
        b["trades"] += 1
        n = _net(t)
        b["pnl"] += n
        if n > 0:
            b["wins"] += 1
        elif n < 0:
            b["losses"] += 1
    out = []
    for symbol, b in buckets.items():
        winrate = (b["wins"] / b["trades"] * 100) if b["trades"] else 0
        out.append(
            {
                "symbol": symbol,
                "trades": b["trades"],
                "wins": b["wins"],
                "losses": b["losses"],
                "pnl": _to_float(b["pnl"]),
                "winrate": round(winrate, 2),
            }
        )
    out.sort(key=lambda r: r["pnl"], reverse=True)
    return out


# --- Smart insights -------------------------------------------------------

OVERTRADE_DAILY_THRESHOLD = 10  # trades/day considered "overtrading"
REVENGE_TRADE_WINDOW_MIN = 30  # mins after a loss
REVENGE_TRADE_SIZE_MULTIPLIER = Decimal("1.5")  # bigger size after loss


def insights(qs: QuerySet[Trade]) -> dict[str, Any]:
    trades = list(qs.order_by("open_time", "id"))
    n = len(trades)
    findings: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}

    if n == 0:
        return {
            "score": 50,
            "findings": [
                {
                    "kind": "info",
                    "title": "No trades yet",
                    "detail": "Import your MT5 history (CSV / JSON) to unlock insights.",
                }
            ],
            "metrics": {},
        }

    # --- Overtrading: count days with > threshold trades.
    by_day: Counter[date] = Counter()
    for t in trades:
        by_day[t.open_time.date()] += 1
    overtrade_days = [d for d, c in by_day.items() if c >= OVERTRADE_DAILY_THRESHOLD]
    metrics["max_trades_in_a_day"] = max(by_day.values()) if by_day else 0
    metrics["overtrade_days"] = len(overtrade_days)
    if overtrade_days:
        findings.append(
            {
                "kind": "warning",
                "title": "Overtrading detected",
                "detail": (
                    f"You traded ≥{OVERTRADE_DAILY_THRESHOLD} times on "
                    f"{len(overtrade_days)} day(s). Pros usually take 1–5 high-quality setups."
                ),
            }
        )

    # --- Revenge trading: a losing trade quickly followed by a larger trade in the same symbol.
    revenge_count = 0
    for prev, cur in zip(trades, trades[1:], strict=False):
        if _net(prev) >= 0:
            continue
        if cur.symbol != prev.symbol:
            continue
        delta = cur.open_time - prev.close_time
        if timedelta(0) <= delta <= timedelta(minutes=REVENGE_TRADE_WINDOW_MIN):
            if (cur.volume or ZERO) >= (prev.volume or ZERO) * REVENGE_TRADE_SIZE_MULTIPLIER:
                revenge_count += 1
    metrics["revenge_trades"] = revenge_count
    if revenge_count:
        findings.append(
            {
                "kind": "danger",
                "title": "Revenge trading pattern",
                "detail": (
                    f"{revenge_count} time(s) you re-entered the same symbol with a bigger size "
                    f"within {REVENGE_TRADE_WINDOW_MIN} minutes of a losing trade."
                ),
            }
        )

    # --- Risk/reward: average win vs average loss.
    s = summary(qs)
    avg_win = s["average_win"]
    avg_loss = abs(s["average_loss"])
    rr = (avg_win / avg_loss) if avg_loss > 0 else 0
    metrics["risk_reward"] = round(rr, 2)
    metrics["winrate"] = s["winrate"]
    metrics["profit_factor"] = s["profit_factor"]
    if avg_loss > 0 and rr < 1.0:
        findings.append(
            {
                "kind": "warning",
                "title": "You lose more than you win",
                "detail": (
                    f"Your average loss (${avg_loss:.2f}) is bigger than your average "
                    f"win (${avg_win:.2f}). Aim for R:R ≥ 1.5."
                ),
            }
        )
    elif avg_loss > 0 and rr >= 1.5 and s["winrate"] >= 40:
        findings.append(
            {
                "kind": "success",
                "title": "Solid edge",
                "detail": (
                    f"Profitable expectancy: R:R {rr:.2f}, winrate {s['winrate']}%. "
                    f"Stay consistent."
                ),
            }
        )

    # --- Profitability streak.
    if s["total_pnl"] > 0:
        findings.append(
            {
                "kind": "success",
                "title": "Strategy is net profitable",
                "detail": (
                    f"Across {s['total_trades']} trades, total PnL is "
                    f"${s['total_pnl']:.2f} (profit factor {s['profit_factor']})."
                ),
            }
        )
    else:
        findings.append(
            {
                "kind": "danger",
                "title": "Strategy is currently losing money",
                "detail": (
                    f"Total PnL on {s['total_trades']} trades is ${s['total_pnl']:.2f}. "
                    f"Review your setups and risk management."
                ),
            }
        )

    # --- Trader score (0..100).
    score = _score(s, revenge_count, len(overtrade_days), n)
    metrics["score"] = score
    return {"score": score, "findings": findings, "metrics": metrics}


def _score(s: dict[str, Any], revenge: int, overtrade_days: int, total: int) -> int:
    """Composite score 0..100. Weights chosen to feel right, not optimal."""
    # Winrate component (0-30): 50% winrate -> 25, 60%+ -> 30.
    winrate_pts = min(30, s["winrate"] * 0.5)
    # Profit factor component (0-30): pf 2 -> 30.
    pf = s["profit_factor"]
    pf_pts = min(30, pf * 15)
    # Risk/Reward component (0-20).
    avg_loss = abs(s["average_loss"])
    rr = (s["average_win"] / avg_loss) if avg_loss > 0 else 0
    rr_pts = min(20, rr * 10)
    # Discipline penalty.
    discipline_penalty = min(40, revenge * 5 + overtrade_days * 3)
    # Sample-size bonus (0-20): 30 trades -> 10, 100+ -> 20.
    sample_pts = min(20, total / 5)

    raw = winrate_pts + pf_pts + rr_pts + sample_pts - discipline_penalty
    return max(0, min(100, int(round(raw))))
