"""Authentication endpoints: register, login, me, regenerate token.

This module exposes the minimal endpoints required to support a multi-user
deployment of the Trading Journal. Authentication is token-based (DRF
``TokenAuthentication``) so the same token works for both the web dashboard
(stored in browser ``localStorage``) and the bridge daemon (passed via
``--api-token`` / ``BRIDGE_API_TOKEN``).
"""

from __future__ import annotations

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

User = get_user_model()


class _RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(min_length=8, write_only=True)

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Username already taken.")
        return value

    def validate(self, attrs: dict) -> dict:
        # Run Django's password validators *with* a candidate user so that
        # UserAttributeSimilarityValidator (configured in settings.py) can
        # actually compare against username/email — passing user=None silently
        # disables that check.
        candidate = User(
            username=attrs.get("username", ""),
            email=attrs.get("email", "") or "",
        )
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs


class _LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


def _user_payload(user, token: Token) -> dict:
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "date_joined": user.date_joined.isoformat() if user.date_joined else None,
        },
        "token": token.key,
    }


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def register(request: Request) -> Response:
    """Create a new user account and return its auth token."""
    serializer = _RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        # ``validate_username`` does a SELECT-then-create which is racy under
        # concurrent requests. The DB-level unique constraint is the source of
        # truth; if a sibling request beats us to it, surface a 400 instead of
        # leaking a 500 IntegrityError.
        with transaction.atomic():
            user = User.objects.create_user(
                username=data["username"],
                email=data.get("email") or "",
                password=data["password"],
            )
    except IntegrityError:
        return Response(
            {"username": ["Username already taken."]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    token, _ = Token.objects.get_or_create(user=user)
    return Response(_user_payload(user, token), status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login(request: Request) -> Response:
    """Authenticate username + password, returning a token."""
    serializer = _LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    user = authenticate(
        request=request,
        username=data["username"],
        password=data["password"],
    )
    if user is None or not user.is_active:
        return Response(
            {"detail": "Invalid username or password."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    token, _ = Token.objects.get_or_create(user=user)
    return Response(_user_payload(user, token))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request: Request) -> Response:
    """Return the current user's profile + their existing API token."""
    token, _ = Token.objects.get_or_create(user=request.user)
    return Response(_user_payload(request.user, token))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def regenerate_token(request: Request) -> Response:
    """Rotate the user's API token (e.g. after a leak). Old token stops working."""
    # Wrap delete+create so a crash between the two can't leave the user
    # tokenless and locked out — same pattern as ``bridge_regenerate_token``.
    with transaction.atomic():
        Token.objects.filter(user=request.user).delete()
        token = Token.objects.create(user=request.user)
    return Response(_user_payload(request.user, token))
