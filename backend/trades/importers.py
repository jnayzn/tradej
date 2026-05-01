"""CSV / JSON importers for MT5-style trade history exports."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .models import Trade

# Common header aliases seen in MT5 CSV exports and third-party tools.
HEADER_ALIASES: dict[str, str] = {
    # ticket
    "ticket": "ticket",
    "deal": "ticket",
    "position": "ticket",
    "position_id": "ticket",
    "id": "ticket",
    # symbol
    "symbol": "symbol",
    "instrument": "symbol",
    "pair": "symbol",
    # type
    "type": "order_type",
    "order_type": "order_type",
    "side": "order_type",
    "direction": "order_type",
    # volume
    "volume": "volume",
    "lots": "volume",
    "size": "volume",
    "qty": "volume",
    "quantity": "volume",
    # times
    "open_time": "open_time",
    "opentime": "open_time",
    "time": "open_time",
    "open": "open_time",
    "open_date": "open_time",
    "close_time": "close_time",
    "closetime": "close_time",
    "close": "close_time",
    "close_date": "close_time",
    # prices
    "open_price": "open_price",
    "openprice": "open_price",
    "price_open": "open_price",
    "entry": "open_price",
    "entry_price": "open_price",
    "close_price": "close_price",
    "closeprice": "close_price",
    "price_close": "close_price",
    "exit": "close_price",
    "exit_price": "close_price",
    # money
    "profit": "profit",
    "pnl": "profit",
    "p/l": "profit",
    "net": "profit",
    "commission": "commission",
    "fees": "commission",
    "fee": "commission",
    "swap": "swap",
    "rollover": "swap",
    # extras
    "comment": "comment",
    "magic": "magic_number",
    "magic_number": "magic_number",
    "mae": "mae",
    "mfe": "mfe",
    "notes": "notes",
}


@dataclass
class ImportResult:
    created: int
    updated: int
    skipped: int
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
        }


def _normalize_key(key: str) -> str:
    return key.strip().lower().replace(" ", "_").replace("-", "_")


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, int | float | Decimal):
        return Decimal(str(value))
    text = str(value).strip().replace(",", "").replace(" ", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    # Try ISO 8601 first.
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        pass
    # Common MT5 format: "2024.05.01 14:23:00"
    for fmt in (
        "%Y.%m.%d %H:%M:%S",
        "%Y.%m.%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _parse_order_type(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text.startswith("b") or text in {"long", "0"}:
        return Trade.OrderType.BUY
    if text.startswith("s") or text in {"short", "1"}:
        return Trade.OrderType.SELL
    return None


def _normalize_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a raw row (CSV dict or JSON object) onto Trade field names."""
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if k is None:
            continue
        key = HEADER_ALIASES.get(_normalize_key(str(k)))
        if not key:
            continue
        out[key] = v
    return out


def _build_trade_kwargs(record: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Convert a normalized record into kwargs ready for `Trade(**kwargs)`.

    Returns (kwargs, None) on success or (None, error_message) on failure.
    """
    symbol = (record.get("symbol") or "").strip().upper() if record.get("symbol") else ""
    if not symbol:
        return None, "missing symbol"

    order_type = _parse_order_type(record.get("order_type"))
    if not order_type:
        return None, f"unknown order type for {symbol}"

    open_time = _parse_datetime(record.get("open_time"))
    close_time = _parse_datetime(record.get("close_time")) or open_time
    if not open_time:
        return None, f"missing open_time for {symbol}"
    if not close_time:
        close_time = open_time

    kwargs: dict[str, Any] = {
        "symbol": symbol,
        "order_type": order_type,
        "open_time": open_time,
        "close_time": close_time,
        "volume": _parse_decimal(record.get("volume")) or Decimal("0"),
        "open_price": _parse_decimal(record.get("open_price")) or Decimal("0"),
        "close_price": _parse_decimal(record.get("close_price")) or Decimal("0"),
        "profit": _parse_decimal(record.get("profit")) or Decimal("0"),
        "commission": _parse_decimal(record.get("commission")) or Decimal("0"),
        "swap": _parse_decimal(record.get("swap")) or Decimal("0"),
        "comment": str(record.get("comment") or "")[:255],
        "notes": str(record.get("notes") or ""),
    }
    if record.get("ticket") not in (None, ""):
        try:
            kwargs["ticket"] = int(str(record["ticket"]).strip())
        except (TypeError, ValueError):
            pass
    if record.get("magic_number") not in (None, ""):
        try:
            kwargs["magic_number"] = int(str(record["magic_number"]).strip())
        except (TypeError, ValueError):
            pass
    if (mae := _parse_decimal(record.get("mae"))) is not None:
        kwargs["mae"] = mae
    if (mfe := _parse_decimal(record.get("mfe"))) is not None:
        kwargs["mfe"] = mfe
    return kwargs, None


def import_records(records: list[dict[str, Any]]) -> ImportResult:
    """Insert / update a batch of normalized records.

    Records with a non-null `ticket` are upserted; others are always created.
    """
    created = updated = skipped = 0
    errors: list[str] = []
    for idx, raw in enumerate(records, start=1):
        normalized = _normalize_record(raw)
        kwargs, err = _build_trade_kwargs(normalized)
        if err:
            skipped += 1
            errors.append(f"row {idx}: {err}")
            continue
        ticket = kwargs.get("ticket")
        if ticket is not None:
            obj, was_created = Trade.objects.update_or_create(
                ticket=ticket,
                defaults={k: v for k, v in kwargs.items() if k != "ticket"},
            )
            if was_created:
                created += 1
            else:
                updated += 1
        else:
            Trade.objects.create(**kwargs)
            created += 1
    return ImportResult(created=created, updated=updated, skipped=skipped, errors=errors)


def parse_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def parse_json(text: str) -> list[dict[str, Any]]:
    data = json.loads(text)
    if isinstance(data, dict):
        # Allow a wrapper like {"trades": [...]}
        for key in ("trades", "data", "results", "items"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError("JSON payload must be a list or {trades: [...]}")
