from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"trades", views.TradeViewSet, basename="trade")

urlpatterns = [
    path("", include(router.urls)),
    path("stats/summary/", views.stats_summary, name="stats-summary"),
    path("stats/equity/", views.stats_equity, name="stats-equity"),
    path("stats/calendar/", views.stats_calendar, name="stats-calendar"),
    path("stats/by-symbol/", views.stats_by_symbol, name="stats-by-symbol"),
    path("stats/insights/", views.stats_insights, name="stats-insights"),
]
