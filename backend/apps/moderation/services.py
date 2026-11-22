from dataclasses import dataclass

from django.contrib.contenttypes.models import ContentType
from rest_framework.exceptions import ValidationError

from .models import ModAction


def log_mod_action(
    community, *, actor=None, action: str, target=None, detail: str = "", reason=None
) -> None:
    """Append an entry to the community's moderation audit log.

    `reason` is a RemovalInfo; its text is copied so later template edits leave the log intact.
    """
    kwargs = {"community": community, "actor": actor, "action": action, "detail": detail}
    if reason is not None:
        kwargs.update(reason_title=reason.title, reason_body=reason.body, reason_note=reason.note)
    if target is not None:
        kwargs["content_type"] = ContentType.objects.get_for_model(target.__class__)
        kwargs["object_id"] = target.pk
    ModAction.objects.create(**kwargs)


REMOVAL_NOTE_MAX = 500


@dataclass(frozen=True)
class RemovalInfo:
    title: str
    body: str
    note: str

    def body_html(self) -> str:
        from apps.common.markdown import render_markdown

        return render_markdown(f"{self.body}\n\n{self.note}".strip())


def parse_removal(request, community) -> RemovalInfo | None:
    """Read and validate `removal_reason`/`removal_note` for a moderator removal.

    Raises 400 before anything is changed, so a rejected request removes nothing.
    """
    from .models import RemovalReason

    data = request.data if hasattr(request.data, "get") else {}
    raw_id = data.get("removal_reason")
    note = str(data.get("removal_note") or "").strip()
    if len(note) > REMOVAL_NOTE_MAX:
        raise ValidationError({"removal_note": f"At most {REMOVAL_NOTE_MAX} characters."})
    if raw_id in (None, ""):
        # A requirement with no templates to pick from would block every removal.
        if community.require_removal_reason and community.removal_reasons.exists():
            raise ValidationError({"removal_reason": "A removal reason is required."})
        return None
    try:
        reason = RemovalReason.objects.filter(community=community, pk=int(raw_id)).first()
    except (TypeError, ValueError):
        reason = None
    if reason is None:
        raise ValidationError({"removal_reason": "Unknown removal reason."})
    return RemovalInfo(title=reason.title, body=reason.body, note=note)


def notify_removal(recipient, actor, target, reason: RemovalInfo | None) -> None:
    """Tell the content owner their content was removed; falls back to the generic notice."""
    from apps.notifications.services import notify

    if reason is None:
        notify(recipient, actor=actor, verb="mod_action", target=target)
        return
    notify(
        recipient,
        actor=actor,
        verb="removal",
        target=target,
        reason_title=reason.title,
        reason_body_html=reason.body_html(),
    )
