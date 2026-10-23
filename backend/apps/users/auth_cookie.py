from django.conf import settings
from rest_framework.response import Response


def _cookie() -> dict:
    return settings.AUTH_REFRESH_COOKIE


def refresh_from_cookie(request) -> str:
    return request.COOKIES.get(_cookie()["key"], "")


def with_refresh_cookie(response: Response) -> Response:
    """Move the refresh token from the body into the HttpOnly cookie, out of reach of page scripts."""
    refresh = response.data.pop("refresh", None) if isinstance(response.data, dict) else None
    if refresh:
        cookie = _cookie()
        response.set_cookie(
            cookie["key"],
            refresh,
            max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
            path=cookie["path"],
            secure=cookie["secure"],
            httponly=True,
            samesite=cookie["samesite"],
        )
    return response


def clear_refresh_cookie(response: Response) -> Response:
    cookie = _cookie()
    response.delete_cookie(cookie["key"], path=cookie["path"], samesite=cookie["samesite"])
    return response
