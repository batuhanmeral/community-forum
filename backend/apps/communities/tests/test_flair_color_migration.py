import importlib

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.communities.models import Community, Flair

User = get_user_model()


@pytest.mark.django_db
class TestFlairColor:
    def test_normalize_colors_resets_only_invalid(self):
        user = User.objects.create_user(username="alice", email="a@x.com", password="x")
        community = Community.objects.create(slug="py", name="Python", creator=user)
        # ORM create skips validators, so legacy bad rows can be seeded
        for name, color in [("a", "red"), ("b", "#ABCDEF"), ("c", "#12345")]:
            Flair.objects.create(community=community, name=name, color=color)

        migration = importlib.import_module("apps.communities.migrations.0010_flair_color_hex")
        migration.normalize_colors(apps, None)

        colors = dict(Flair.objects.values_list("name", "color"))
        assert colors == {"a": "#888888", "b": "#ABCDEF", "c": "#888888"}

    def test_model_rejects_non_hex_color(self):
        user = User.objects.create_user(username="alice", email="a@x.com", password="x")
        community = Community.objects.create(slug="py", name="Python", creator=user)
        with pytest.raises(ValidationError) as exc:
            Flair(community=community, name="n", color="red").full_clean()
        assert "color" in exc.value.message_dict
