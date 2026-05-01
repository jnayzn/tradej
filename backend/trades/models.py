"""Trade model — single canonical record of a closed position."""

from __future__ import annotations

from decimal import Decimal

from django.db import models


class Trade(models.Model):
    """A single closed trade.

    Designed to map cleanly onto the MetaTrader 5 deal/position history while
    remaining usable for trades imported from arbitrary CSV/JSON sources.
    """

    class OrderType(models.TextChoices):
        BUY = "BUY", "Buy"
        SELL = "SELL", "Sell"

    ticket = models.BigIntegerField(
        unique=True,
        null=True,
        blank=True,
        help_text="MT5 deal/position ticket. Used for deduplication when importing.",
    )
    symbol = models.CharField(max_length=32, db_index=True)
    order_type = models.CharField(max_length=8, choices=OrderType.choices)
    volume = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("0"))

    open_time = models.DateTimeField(db_index=True)
    close_time = models.DateTimeField(db_index=True)

    open_price = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal("0"))
    close_price = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal("0"))

    profit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    commission = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    swap = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))

    comment = models.CharField(max_length=255, blank=True, default="")
    magic_number = models.BigIntegerField(null=True, blank=True)

    mae = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum Adverse Excursion (in account currency).",
    )
    mfe = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum Favorable Excursion (in account currency).",
    )

    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-close_time", "-id"]
        indexes = [
            models.Index(fields=["close_time"]),
            models.Index(fields=["symbol", "close_time"]),
        ]

    def __str__(self) -> str:
        return f"{self.symbol} {self.order_type} {self.volume} → {self.profit}"

    @property
    def net_profit(self) -> Decimal:
        """Profit including commission and swap."""
        return (
            (self.profit or Decimal("0"))
            + (self.commission or Decimal("0"))
            + (self.swap or Decimal("0"))
        )

    @property
    def is_win(self) -> bool:
        return self.net_profit > 0

    @property
    def duration_seconds(self) -> int:
        return int((self.close_time - self.open_time).total_seconds())
