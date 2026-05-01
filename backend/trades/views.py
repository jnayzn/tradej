from __future__ import annotations

import json
from datetime import datetime

from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from . import analytics, importers
from .models import Trade
from .serializers import TradeSerializer


class TradeViewSet(viewsets.ModelViewSet):
    queryset = Trade.objects.all()
    serializer_class = TradeSerializer
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    search_fields = ["symbol", "comment", "notes"]
    ordering_fields = ["close_time", "open_time", "profit", "symbol"]
    ordering = ["-close_time"]

    @action(
        detail=False,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser, JSONParser],
        url_path="import",
    )
    def import_trades(self, request: Request) -> Response:
        """Import trades from CSV / JSON (multipart upload, or raw JSON body)."""
        try:
            records = self._extract_records(request)
        except (ValueError, json.JSONDecodeError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not records:
            return Response(
                {"detail": "No records found in payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = importers.import_records(records)
        return Response(result.to_dict(), status=status.HTTP_201_CREATED)

    @staticmethod
    def _extract_records(request: Request) -> list[dict]:
        upload = request.FILES.get("file")
        if upload is not None:
            text = upload.read().decode("utf-8-sig", errors="replace")
            name = (upload.name or "").lower()
            if name.endswith(".json"):
                return importers.parse_json(text)
            return importers.parse_csv(text)

        data = request.data
        if isinstance(data, dict):
            for key in ("trades", "data", "results", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
            if isinstance(data.get("csv"), str):
                return importers.parse_csv(data["csv"])
            if isinstance(data.get("json"), str):
                return importers.parse_json(data["json"])
            return [data]
        if isinstance(data, list):
            return list(data)
        return []


def _base_qs(request: Request):
    qs = Trade.objects.all()
    symbol = request.query_params.get("symbol")
    if symbol:
        qs = qs.filter(symbol__iexact=symbol)
    start = request.query_params.get("start")
    end = request.query_params.get("end")
    if start:
        qs = qs.filter(close_time__gte=start)
    if end:
        qs = qs.filter(close_time__lte=end)
    return qs


@api_view(["GET"])
def stats_summary(request: Request) -> Response:
    return Response(analytics.summary(_base_qs(request)))


@api_view(["GET"])
def stats_equity(request: Request) -> Response:
    return Response({"points": analytics.equity_curve(_base_qs(request))})


@api_view(["GET"])
def stats_calendar(request: Request) -> Response:
    now = timezone.now()
    try:
        year = int(request.query_params.get("year") or now.year)
        month = int(request.query_params.get("month") or now.month)
    except ValueError:
        return Response({"detail": "year and month must be integers."}, status=400)
    if not (1 <= month <= 12):
        return Response({"detail": "month must be between 1 and 12."}, status=400)
    if not (1970 <= year <= datetime.max.year):
        return Response({"detail": "invalid year."}, status=400)
    return Response(analytics.calendar_view(_base_qs(request), year, month))


@api_view(["GET"])
def stats_by_symbol(request: Request) -> Response:
    return Response({"symbols": analytics.by_symbol(_base_qs(request))})


@api_view(["GET"])
def stats_insights(request: Request) -> Response:
    return Response(analytics.insights(_base_qs(request)))
