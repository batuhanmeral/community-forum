import pytest
from django.contrib.auth import get_user_model

from apps.comments.lib.mentions import extract_mention_usernames, resolve_mentions

User = get_user_model()


class TestExtract:
    @pytest.mark.parametrize(
        "body, expected",
        [
            pytest.param("", [], id="empty"),
            pytest.param("hello @alice!", ["alice"], id="single"),
            pytest.param("@alice @bob @alice", ["alice", "bob"], id="duplicates-preserve-order"),
            pytest.param(
                "@Alice @ALICE @bob", ["Alice", "bob"], id="case-insensitive-deduplication"
            ),
            pytest.param("contact me at user@bob.com", [], id="email"),
            pytest.param("hi @user_42", ["user_42"], id="underscore-and-digits"),
        ],
    )
    def test_extract_mention_usernames(self, body, expected):
        assert extract_mention_usernames(body) == expected


@pytest.mark.django_db
class TestResolve:
    def test_resolves_existing_users(self):
        alice = User.objects.create_user(username="alice", email="a@x.com", password="x")
        User.objects.create_user(username="bob", email="b@x.com", password="x")
        users = resolve_mentions("hi @alice and @bob and @ghost")
        names = sorted(u.username for u in users)
        assert names == ["alice", "bob"]
        assert alice in users

    def test_excludes_actor(self):
        alice = User.objects.create_user(username="alice", email="a@x.com", password="x")
        bob = User.objects.create_user(username="bob", email="b@x.com", password="x")
        users = resolve_mentions("@alice @bob", exclude_user=alice)
        assert users == [bob]
