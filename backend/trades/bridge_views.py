"""Bridge endpoints — passwordless single-user mode.

This module exposes the endpoints the MT5 Bridge page needs to operate the
"share with friends, one instance per friend" deployment model:

* ``GET   /api/bridge/info/``            → owner's token + last sync (auto-
  creates the owner on first call). **Public** — anyone who can reach the
  URL is treated as the owner. Only safe when each friend deploys their
  own instance.
* ``GET   /api/bridge/script/``          → serves the bridge script as
  ``tradj_bridge.py`` for download.
* ``POST  /api/bridge/regenerate-token/`` → rotates the owner's token.
* ``PATCH /api/bridge/profile/``         → rename the owner (set a custom
  display username). Bridge token is preserved.

The User + Token machinery is preserved in the database so per-user trade
isolation keeps working — there just happens to be only one user per
deployment.
"""

from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import FileResponse, Http404
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Trade

User = get_user_model()

USERNAME_MIN_LEN = 2
USERNAME_MAX_LEN = 32


def _owner_username() -> str:
    return os.environ.get("TRADEJ_OWNER_USERNAME", "owner")


def _get_or_create_owner() -> User:
    """Return the singleton owner user, preferring an existing one over the
    default name. Once renamed, ``TRADEJ_OWNER_USERNAME`` no longer matters
    — we keep using whichever owner already exists."""
    user = User.objects.order_by("id").first()
    if user is not None:
        return user
    user, _ = User.objects.get_or_create(
        username=_owner_username(),
        defaults={"email": "", "is_active": True},
    )
    return user


def _last_sync_at(user: User) -> str | None:
    last = (
        Trade.objects.filter(user=user)
        .aggregate(latest=Max("created_at"))
        .get("latest")
    )
    return last.isoformat() if last else None


def _info_payload(user: User, token: Token) -> dict:
    return {
        "owner_username": user.username,
        "token": token.key,
        "last_sync_at": _last_sync_at(user),
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
    }


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def bridge_info(request: Request) -> Response:
    """Return the owner's API token, last-sync timestamp, and account
    creation date.

    Auto-creates the singleton owner user on first call so a freshly
    deployed instance "just works" without a manual ``createsuperuser``.
    """
    with transaction.atomic():
        user = _get_or_create_owner()
        token, _ = Token.objects.get_or_create(user=user)
    return Response(_info_payload(user, token))


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def bridge_regenerate_token(request: Request) -> Response:
    """Rotate the owner's API token. Old token stops working immediately."""
    with transaction.atomic():
        user = _get_or_create_owner()
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)
    return Response(_info_payload(user, token))


@api_view(["PATCH"])
@authentication_classes([])
@permission_classes([AllowAny])
def bridge_update_profile(request: Request) -> Response:
    """Rename the owner (display username). Token is preserved.

    Accepts a JSON body with an optional ``username`` field. Other fields
    are ignored. Validation is intentionally minimal — this is the
    single-user "set my display name" flow, not a full account editor.
    """
    raw_username = request.data.get("username")
    if raw_username is None or not isinstance(raw_username, str):
        return Response(
            {"username": ["This field is required."]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    new_username = raw_username.strip()
    if len(new_username) < USERNAME_MIN_LEN or len(new_username) > USERNAME_MAX_LEN:
        return Response(
            {
                "username": [
                    f"Must be between {USERNAME_MIN_LEN} and "
                    f"{USERNAME_MAX_LEN} characters."
                ]
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    # Reject obviously broken values; allow letters, digits, _, -, ., space.
    if not all(ch.isalnum() or ch in "-_.@ " for ch in new_username):
        return Response(
            {"username": ["Only letters, digits, and -_.@ space are allowed."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            user = _get_or_create_owner()
            if user.username != new_username:
                user.username = new_username
                user.save(update_fields=["username"])
            token, _ = Token.objects.get_or_create(user=user)
    except IntegrityError:
        return Response(
            {"username": ["That username is already taken."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(_info_payload(user, token))


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def bridge_script(request: Request) -> FileResponse:
    """Serve the MT5 bridge Python script as ``tradj_bridge.py``."""
    # Resolve ``<repo>/bridge/mt5_bridge.py`` regardless of where the Django
    # app was started from. Allow override via env var so packagers (Docker,
    # Railway, etc.) can ship the script next to the app.
    candidate_paths = [
        os.environ.get("TRADEJ_BRIDGE_SCRIPT_PATH"),
        str(Path(settings.BASE_DIR).parent / "bridge" / "mt5_bridge.py"),
        str(Path(settings.BASE_DIR) / "bridge" / "mt5_bridge.py"),
    ]
    for raw in candidate_paths:
        if not raw:
            continue
        path = Path(raw)
        if path.exists() and path.is_file():
            return FileResponse(
                open(path, "rb"),
                as_attachment=True,
                filename="tradj_bridge.py",
                content_type="text/x-python",
            )
    raise Http404("bridge script not found on server")
