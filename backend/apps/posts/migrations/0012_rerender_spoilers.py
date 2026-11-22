from django.db import migrations

from apps.common.rendered_body import backfill_body_html


def rerender(apps, schema_editor):
    # `>!text!<` used to render as escaped text; bodies are re-rendered once for the new rule.
    backfill_body_html(apps.get_model("posts", "Post"))


class Migration(migrations.Migration):
    dependencies = [("posts", "0011_spoiler_post_flag")]

    operations = [migrations.RunPython(rerender, migrations.RunPython.noop)]
