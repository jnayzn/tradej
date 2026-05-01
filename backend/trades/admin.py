from django.contrib import admin

from .models import Trade


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "ticket",
        "symbol",
        "order_type",
        "volume",
        "open_time",
        "close_time",
        "profit",
        "commission",
        "swap",
    )
    list_filter = ("symbol", "order_type")
    search_fields = ("symbol", "comment", "ticket")
    date_hierarchy = "close_time"
