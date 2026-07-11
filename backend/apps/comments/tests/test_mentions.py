import pytest
from django.contrib.auth import get_user_model

from apps.comments.lib.mentions import extract_mention_usernames, resolve_mentions

User = get_user_model()


class TestExtract:
    def test_empty(self):
        assert extract_mention_usernames("") == []

    def test_single(self):
        assert extract_mention_usernames("hello @alice!") == ["alice"]

    def test_multiple_unique(self):
        assert extract_mention_usernames("@alice @bob @alice") == ["alice", "bob"]

    def test_case_insensitive_dedupe(self):
        assert extract_mention_usernames("@Alice @ALICE @bob") == ["Alice", "bob"]

    def test_ignores_email(self):
        # "@bob" after a letter (in email) should NOT match
        assert extract_mention_usernames("contact me at user@bob.com") == []

    def test_underscore_allowed(self):
        assert extract_mention_usernames("hi @user_42") == ["user_42"]


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
