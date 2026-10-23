import re

from django.contrib.auth import get_user_model

from apps.common.markdown import MENTION_RE

User = get_user_model()

MAX_MENTIONS = 10


def extract_mention_usernames(body: str) -> list[str]:
    """Return unique, order-preserving @usernames in body, at most MAX_MENTIONS."""
    if not body:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in MENTION_RE.finditer(body):
        name = m.group(1)
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
        if len(out) == MAX_MENTIONS:
            break
    return out


def resolve_mentions(body: str, exclude_user=None) -> list:
    """Return User objects mentioned in body (case-insensitive), excluding `exclude_user`."""
    names = extract_mention_usernames(body)
    if not names:
        return []
    qs = User.objects.filter(
        is_active=True,
        username__iregex=r"^(" + "|".join(re.escape(n) for n in names) + r")$",
    )
    if exclude_user is not None and getattr(exclude_user, "id", None):
        qs = qs.exclude(pk=exclude_user.pk)
    return list(qs)
