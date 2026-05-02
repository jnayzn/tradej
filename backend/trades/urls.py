from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import auth_views, views

router = DefaultRouter()
router.register(r"trades", views.TradeViewSet, basename="trade")

urlpatterns = [
    path("", include(router.urls)),
    path("stats/summary/", views.stats_summary, name="stats-summary"),
    path("stats/equity/", views.stats_equity, name="stats-equity"),
    path("stats/calendar/", views.stats_calendar, name="stats-calendar"),
    path("stats/by-symbol/", views.stats_by_symbol, name="stats-by-symbol"),
    path("stats/insights/", views.stats_insights, name="stats-insights"),
    path("auth/register/", auth_views.register, name="auth-register"),
    path("auth/login/", auth_views.login, name="auth-login"),
    path("auth/me/", auth_views.me, name="auth-me"),
    path(
        "auth/regenerate-token/",
        auth_views.regenerate_token,
        name="auth-regenerate-token",
    ),
]
