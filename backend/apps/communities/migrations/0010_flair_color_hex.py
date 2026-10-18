import django.core.validators
from django.db import migrations, models

# Frozen copies: migrations must not depend on values that may change in models.py.
HEX_COLOR_PATTERN = r"^#[0-9a-fA-F]{6}\Z"
DEFAULT_FLAIR_COLOR = "#888888"


def normalize_colors(apps, schema_editor):
    Flair = apps.get_model("communities", "Flair")
    Flair.objects.exclude(color__regex=HEX_COLOR_PATTERN).update(color=DEFAULT_FLAIR_COLOR)


class Migration(migrations.Migration):

    dependencies = [
        ('communities', '0009_text_length_caps'),
    ]

    operations = [
        migrations.RunPython(normalize_colors, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='flair',
            name='color',
            field=models.CharField(default='#888888', max_length=7, validators=[django.core.validators.RegexValidator('^#[0-9a-fA-F]{6}\\Z')]),
        ),
    ]
