from django.db import migrations


def unpin_removed(apps, schema_editor):
    Post = apps.get_model("posts", "Post")
    Post.objects.filter(is_pinned=True, deleted_at__isnull=False).update(is_pinned=False)


class Migration(migrations.Migration):
    dependencies = [("posts", "0005_post_is_approved")]

    operations = [migrations.RunPython(unpin_removed, migrations.RunPython.noop)]
