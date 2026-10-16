import logging

from django.db import DatabaseError, connection
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .markdown import render_markdown

logger = logging.getLogger(__name__)

MAX_PREVIEW_CHARS = 40_000


class MarkdownPreviewSerializer(serializers.Serializer):
    body = serializers.CharField(allow_blank=True, max_length=MAX_PREVIEW_CHARS)


class MarkdownPreviewView(APIView):
    """Render markdown with the exact pipeline used for stored content."""

    permission_classes = (permissions.IsAuthenticated,)
    throttle_scope = "write"

    def post(self, request):
        serializer = MarkdownPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({"html": render_markdown(serializer.validated_data["body"])})


class HealthView(APIView):
    """Liveness/readiness probe for the orchestrator; never exposes error details."""

    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)
    throttle_classes = ()

    def get(self, request):
        try:
            connection.ensure_connection()
        except DatabaseError as exc:
            logger.warning("Health check failed: %s", type(exc).__name__)
            return Response({"status": "unavailable"}, status=503)
        return Response({"status": "ok"})
