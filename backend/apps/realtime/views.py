from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .groups import realtime_enabled
from .tickets import issue_ticket


def _token_expiry(token) -> float | None:
    exp = token.get("exp") if token is not None else None
    return float(exp) if exp is not None else None


class TicketView(APIView):
    """Exchange the caller's JWT for a short-lived, one-time WebSocket ticket."""

    permission_classes = (permissions.IsAuthenticated,)
    throttle_scope = "realtime_ticket"

    def post(self, request):
        if not realtime_enabled():
            # The client treats this as "keep polling".
            return Response(
                {"detail": "Realtime is disabled."}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        response = Response(
            {
                # request.auth is the validated access token; its exp bounds the socket.
                "ticket": issue_ticket(request.user, expires_at=_token_expiry(request.auth)),
                "expires_in": settings.REALTIME_TICKET_TTL,
            },
            status=status.HTTP_201_CREATED,
        )
        response["Cache-Control"] = "no-store"
        return response
