from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.polls.models import Poll, PollOption, PollVote
from apps.posts.models import Post

User = get_user_model()

FEED = reverse("api_v1:feed:feed")
OPTION_VOTES = [2, 1, 1, 0, 0]


def post_detail(pk):
    return reverse("api_v1:posts:post-detail", args=[pk])


def poll_detail(pk):
    return reverse("api_v1:polls:poll-detail", args=[pk])


def poll_vote(pk):
    return reverse("api_v1:polls:poll-vote", args=[pk])


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def author(db):
    return User.objects.create_user(username="author", email="author@x.com", password="x")


@pytest.fixture
def viewer(db):
    return User.objects.create_user(username="viewer", email="viewer@x.com", password="x")


@pytest.fixture
def voters(db):
    return [
        User.objects.create_user(username=f"voter{i}", email=f"voter{i}@x.com", password="x")
        for i in range(4)
    ]


@pytest.fixture
def community(author, viewer):
    c = Community.objects.create(slug="py", name="Python", creator=author)
    Membership.objects.create(user=viewer, community=c)
    return c


@pytest.fixture
def make_poll(author, community):
    def _make(title="poll"):
        post = Post.objects.create(author=author, community=community, kind="poll", title=title)
        poll = Poll.objects.create(post=post, closes_at=timezone.now() + timedelta(days=1))
        options = [PollOption.objects.create(poll=poll, text=f"opt{i}", order=i) for i in range(5)]
        return poll, options

    return _make


def cast(poll, options, users, per_option=OPTION_VOTES):
    """Distributes users over options following per_option counts."""
    it = iter(users)
    for option, count in zip(options, per_option, strict=True):
        for _ in range(count):
            PollVote.objects.create(poll=poll, option=option, user=next(it))


@pytest.fixture
def poll_with_votes(make_poll, voters, viewer):
    poll, options = make_poll()
    # Viewer shares the first option (2 votes) with one other voter.
    cast(poll, options, [viewer, voters[0], voters[1], voters[2]])
    return poll, options


def test_feed_with_poll_posts_has_constant_queries(
    api, viewer, make_poll, voters, django_assert_max_num_queries
):
    for i in range(3):
        poll, options = make_poll(f"poll {i}")
        extra = [
            User.objects.create_user(username=f"f{i}_{n}", email=f"f{i}_{n}@x.com", password="x")
            for n in range(6)
        ]
        cast(poll, options, voters + extra, per_option=[4, 3, 2, 1, 0])
    api.force_authenticate(viewer)
    with django_assert_max_num_queries(12):
        resp = api.get(FEED)
    polls = [p["poll"] for p in resp.data["results"] if p["poll"]]
    assert len(polls) == 3 and polls[0]["total_votes"] == 10


def test_poll_post_detail_queries(api, viewer, poll_with_votes, django_assert_max_num_queries):
    poll, _ = poll_with_votes
    api.force_authenticate(viewer)
    with django_assert_max_num_queries(6):
        assert api.get(post_detail(poll.post_id)).status_code == 200


def test_poll_detail_queries_and_viewer_choice(
    api, viewer, poll_with_votes, django_assert_max_num_queries
):
    poll, options = poll_with_votes
    api.force_authenticate(viewer)
    with django_assert_max_num_queries(4):
        data = api.get(poll_detail(poll.id)).data
    assert data["user_option"] == options[0].id
    assert [o["vote_count"] for o in data["options"]] == OPTION_VOTES


def test_vote_response_counts_the_new_vote(api, viewer, make_poll):
    poll, options = make_poll()
    api.force_authenticate(viewer)
    data = api.post(poll_vote(poll.id), {"option_id": options[2].id}, format="json").data
    assert data["user_option"] == options[2].id
    assert data["total_votes"] == 1
    assert next(o for o in data["options"] if o["id"] == options[2].id)["vote_count"] == 1


def test_anonymous_feed_loads_no_poll_vote_rows(api, poll_with_votes):
    with CaptureQueriesContext(connection) as ctx:
        resp = api.get(FEED)
    assert resp.data["results"][0]["poll"]["user_option"] is None
    assert not [q for q in ctx.captured_queries if 'FROM "polls_pollvote"' in q["sql"]]
