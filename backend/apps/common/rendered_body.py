from django.db import models

from .markdown import render_markdown

BACKFILL_BATCH_SIZE = 500


class RenderedBodyModel(models.Model):
    """Keeps `body_html` in sync with `body` so read paths never run the markdown parser."""

    body_html = models.TextField(blank=True, default="", editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is None or "body" in update_fields:
            self.body_html = render_markdown(self.body)
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "body_html"}
        super().save(*args, **kwargs)


def backfill_body_html(model: type[models.Model], batch_size: int = BACKFILL_BATCH_SIZE) -> None:
    """Re-render every row; migrations call this whenever the renderer's output changes."""
    batch = []
    for row in model.objects.only("id", "body").iterator(chunk_size=batch_size):
        row.body_html = render_markdown(row.body)
        batch.append(row)
        if len(batch) == batch_size:
            model.objects.bulk_update(batch, ["body_html"])
            batch = []
    if batch:
        model.objects.bulk_update(batch, ["body_html"])
