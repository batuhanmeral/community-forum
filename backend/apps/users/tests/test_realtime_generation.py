import pytest
from django.contrib.auth import get_user_model
from django.db import connection

User = get_user_model()


@pytest.mark.django_db
def test_old_app_instances_can_still_insert_users():
    """During a rolling deploy, code without realtime_generation inserts users without it."""
    user = User(username="legacy", email="legacy@example.com")
    user.set_password("x")
    fields = [f for f in User._meta.concrete_fields if f.name not in ("id", "realtime_generation")]
    columns = ", ".join(connection.ops.quote_name(f.column) for f in fields)
    values = [f.get_db_prep_save(f.pre_save(user, True), connection) for f in fields]
    with connection.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO {User._meta.db_table} ({columns}) "
            f"VALUES ({', '.join(['%s'] * len(values))})",
            values,
        )
    assert User.objects.get(username="legacy").realtime_generation == 0


@pytest.mark.django_db
def test_realtime_generation_is_a_bigint():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = 'realtime_generation'",
            [User._meta.db_table],
        )
        assert cursor.fetchone() == ("bigint",)
