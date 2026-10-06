from django.db import migrations, models

from apps.common.rendered_body import backfill_body_html


def backfill(apps, schema_editor):
    backfill_body_html(apps.get_model("comments", "Comment"))


class Migration(migrations.Migration):
    dependencies = [("comments", "0003_comment_edited_at_commentrevision")]

    operations = [
        migrations.AddField(
            model_name="comment",
            name="body_html",
            field=models.TextField(blank=True, default="", editable=False),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
