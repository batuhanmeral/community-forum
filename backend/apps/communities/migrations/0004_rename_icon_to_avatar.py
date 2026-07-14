from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("communities", "0003_community_search_vector_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="community",
            old_name="icon",
            new_name="avatar",
        ),
        migrations.AlterField(
            model_name="community",
            name="avatar",
            field=models.ImageField(
                blank=True, null=True, upload_to="community_avatars/"
            ),
        ),
    ]
