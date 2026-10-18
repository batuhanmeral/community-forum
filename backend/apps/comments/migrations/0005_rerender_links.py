from django.db import migrations

from apps.common.rendered_body import backfill_body_html


def backfill(apps, schema_editor):
    backfill_body_html(apps.get_model("comments", "Comment"))


class Migration(migrations.Migration):
    dependencies = [("comments", "0004_comment_body_html")]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
