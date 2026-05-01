from __future__ import annotations

from rest_framework import serializers

from .models import Trade


class TradeSerializer(serializers.ModelSerializer):
    net_profit = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    is_win = serializers.BooleanField(read_only=True)
    duration_seconds = serializers.IntegerField(read_only=True)

    class Meta:
        model = Trade
        fields = [
            "id",
            "ticket",
            "symbol",
            "order_type",
            "volume",
            "open_time",
            "close_time",
            "open_price",
            "close_price",
            "profit",
            "commission",
            "swap",
            "comment",
            "magic_number",
            "mae",
            "mfe",
            "notes",
            "net_profit",
            "is_win",
            "duration_seconds",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
