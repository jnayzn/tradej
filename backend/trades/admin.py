from django.contrib import admin

from .models import Trade


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
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
    list_filter = ("user", "symbol", "order_type")
    search_fields = ("symbol", "comment", "ticket", "user__username")
    date_hierarchy = "close_time"
