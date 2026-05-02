from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import auth_views, bridge_views, views

router = DefaultRouter()
router.register(r"trades", views.TradeViewSet, basename="trade")

urlpatterns = [
    path("", include(router.urls)),
    path("stats/summary/", views.stats_summary, name="stats-summary"),
    path("stats/equity/", views.stats_equity, name="stats-equity"),
    path("stats/calendar/", views.stats_calendar, name="stats-calendar"),
    path("stats/by-symbol/", views.stats_by_symbol, name="stats-by-symbol"),
    path("stats/insights/", views.stats_insights, name="stats-insights"),
    # Passwordless bridge endpoints (single-user-per-instance deployment).
    path("bridge/info/", bridge_views.bridge_info, name="bridge-info"),
    path("bridge/script/", bridge_views.bridge_script, name="bridge-script"),
    path(
        "bridge/regenerate-token/",
        bridge_views.bridge_regenerate_token,
        name="bridge-regenerate-token",
    ),
    path(
        "bridge/profile/",
        bridge_views.bridge_update_profile,
        name="bridge-update-profile",
    ),
    # Multi-user auth endpoints kept available for instances that opt back into
    # password login. Frontend currently does not use them.
    path("auth/register/", auth_views.register, name="auth-register"),
    path("auth/login/", auth_views.login, name="auth-login"),
    path("auth/me/", auth_views.me, name="auth-me"),
    path(
        "auth/regenerate-token/",
        auth_views.regenerate_token,
        name="auth-regenerate-token",
    ),
]
