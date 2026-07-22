from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .markdown import render_markdown

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
