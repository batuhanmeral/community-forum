"""Backfills run in their own migration, so a schema change never holds its lock through them."""

import pytest
from django.db import migrations
from django.db.migrations.loader import MigrationLoader


@pytest.mark.django_db
def test_no_posts_migration_mixes_schema_changes_with_a_backfill():
    loader = MigrationLoader(None, ignore_no_migrations=True)
    mixed = []
    for (app, name), migration in loader.disk_migrations.items():
        if app != "posts":
            continue
        kinds = {isinstance(op, migrations.RunPython) for op in migration.operations}
        if kinds == {True, False}:
            mixed.append(name)
    # 0007 predates this rule (adds body_html and fills it); it is already applied everywhere.
    assert sorted(mixed) == ["0007_post_body_html"]
    spoiler = loader.disk_migrations[("posts", "0011_spoiler_post_flag")]
    assert [type(op) for op in spoiler.operations] == [migrations.AddField]


@pytest.mark.django_db
def test_the_spoiler_rerender_directly_follows_the_spoiler_flag():
    """Keeps the spoiler feature's migrations together, ahead of later features' ones."""
    loader = MigrationLoader(None, ignore_no_migrations=True)
    rerender = loader.disk_migrations[("posts", "0012_rerender_spoilers")]
    assert rerender.dependencies == [("posts", "0011_spoiler_post_flag")]
    assert [type(op) for op in rerender.operations] == [migrations.RunPython]
