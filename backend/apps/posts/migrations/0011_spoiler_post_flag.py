from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("posts", "0010_qa_question_bounty")]

    # Schema only: the body re-render for the `>!text!<` rule lives in 0012_rerender_spoilers,
    # so this migration's lock on the posts table is not held while every row is rewritten.
    operations = [
        migrations.AddField(
            model_name="post",
            name="is_spoiler",
            field=models.BooleanField(default=False),
        ),
    ]
