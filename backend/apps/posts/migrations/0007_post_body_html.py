from django.db import migrations, models

from apps.common.rendered_body import backfill_body_html


def backfill(apps, schema_editor):
    backfill_body_html(apps.get_model("posts", "Post"))


class Migration(migrations.Migration):
    dependencies = [("posts", "0006_unpin_removed_posts")]

    operations = [
        migrations.AddField(
            model_name="post",
            name="body_html",
            field=models.TextField(blank=True, default="", editable=False),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
