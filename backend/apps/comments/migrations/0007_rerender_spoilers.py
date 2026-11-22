from django.db import migrations

from apps.common.rendered_body import backfill_body_html


def rerender(apps, schema_editor):
    # `>!text!<` used to render as escaped text; bodies are re-rendered once for the new rule.
    backfill_body_html(apps.get_model("comments", "Comment"))


class Migration(migrations.Migration):
    dependencies = [("comments", "0006_rerender_mentions")]

    operations = [migrations.RunPython(rerender, migrations.RunPython.noop)]
