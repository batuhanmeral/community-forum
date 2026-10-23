from django.db import migrations

from apps.common.rendered_body import backfill_body_html


def backfill(apps, schema_editor):
    backfill_body_html(apps.get_model("posts", "Post"))


class Migration(migrations.Migration):
    dependencies = [("posts", "0008_rerender_links")]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
