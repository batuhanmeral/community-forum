import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.posts.models import Post
from apps.votes.models import Vote

User = get_user_model()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="StrongPass123!")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password="StrongPass123!")


@pytest.fixture
def post(alice):
    community = Community.objects.create(slug="py", name="Py", creator=alice)
    return Post.objects.create(author=alice, community=community, title="t")


def _vote(user, target, value=1):
    return Vote.objects.create(
        user=user,
        content_type=ContentType.objects.get_for_model(type(target)),
        object_id=target.id,
        value=value,
    )


@pytest.mark.django_db
class TestSelfVotes:
    def test_self_upvote_on_post_adds_no_karma(self, alice, post):
        _vote(alice, post)
        alice.refresh_from_db()
        assert alice.post_karma == 0

    def test_self_vote_on_comment_adds_no_karma(self, alice, post):
        comment = Comment.objects.create(post=post, author=alice, body="c")
        _vote(alice, comment)
        alice.refresh_from_db()
        assert alice.comment_karma == 0

    def test_removing_a_self_vote_changes_nothing(self, alice, post):
        _vote(alice, post)
        User.objects.filter(pk=alice.pk).update(post_karma=5)
        Vote.objects.filter(user=alice, object_id=post.id).delete()
        alice.refresh_from_db()
        assert alice.post_karma == 5

    def test_flipping_a_self_vote_changes_nothing(self, alice, post):
        vote = _vote(alice, post, value=1)
        vote.value = -1
        vote.save()
        alice.refresh_from_db()
        assert alice.post_karma == 0

    def test_other_votes_still_count(self, alice, bob, post):
        _vote(bob, post)
        alice.refresh_from_db()
        assert alice.post_karma == 1

    def test_recalculate_ignores_self_votes(self, alice, bob, post):
        _vote(alice, post)
        _vote(bob, post)
        User.objects.filter(pk=alice.pk).update(post_karma=99)
        call_command("recalculate_karma")
        alice.refresh_from_db()
        assert alice.post_karma == 1
