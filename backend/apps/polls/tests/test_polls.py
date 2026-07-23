from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.communities.models import Community, Membership
from apps.polls.models import Poll, PollOption, PollVote
from apps.posts.models import Post

User = get_user_model()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="alice", email="a@x.com", password="x")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="bob", email="b@x.com", password="x")


@pytest.fixture
def community(alice):
    return Community.objects.create(slug="py", name="Python", creator=alice)


@pytest.fixture
def join(community):
    def _join(user):
        Membership.objects.get_or_create(user=user, community=community)

    return _join


def post_create_url(slug):
    return reverse("api_v1:community-posts:community-posts", args=[slug])


def poll_vote_url(pk):
    return reverse("api_v1:polls:poll-vote", args=[pk])


def poll_detail_url(pk):
    return reverse("api_v1:polls:poll-detail", args=[pk])


@pytest.mark.django_db
class TestPollCreation:
    def test_poll_post_creates_poll_and_options(self, api, alice, community):
        api.force_authenticate(alice)
        future = (timezone.now() + timedelta(days=1)).isoformat()
        resp = api.post(
            post_create_url("py"),
            {
                "title": "Best lang?",
                "kind": "poll",
                "poll_input": {"closes_at": future, "options": ["Python", "Rust", "Go"]},
            },
            format="json",
        )
        assert resp.status_code == 201, resp.data
        post = Post.objects.get(pk=resp.data["id"])
        assert hasattr(post, "poll")
        assert post.poll.options.count() == 3
        assert resp.data["poll"]["total_votes"] == 0

    def test_poll_post_requires_input(self, api, alice, community):
        api.force_authenticate(alice)
        resp = api.post(
            post_create_url("py"),
            {"title": "x", "kind": "poll"},
            format="json",
        )
        assert resp.status_code == 400
        assert "poll_input" in resp.data

    def test_poll_rejects_past_closes_at(self, api, alice, community):
        api.force_authenticate(alice)
        past = (timezone.now() - timedelta(hours=1)).isoformat()
        resp = api.post(
            post_create_url("py"),
            {
                "title": "x",
                "kind": "poll",
                "poll_input": {"closes_at": past, "options": ["a", "b"]},
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_poll_requires_at_least_two_options(self, api, alice, community):
        api.force_authenticate(alice)
        future = (timezone.now() + timedelta(days=1)).isoformat()
        resp = api.post(
            post_create_url("py"),
            {
                "title": "x",
                "kind": "poll",
                "poll_input": {"closes_at": future, "options": ["solo"]},
            },
            format="json",
        )
        assert resp.status_code == 400


@pytest.fixture
def open_poll(alice, community):
    post = Post.objects.create(author=alice, community=community, kind="poll", title="t")
    poll = Poll.objects.create(post=post, closes_at=timezone.now() + timedelta(days=1))
    opt_a = PollOption.objects.create(poll=poll, text="A", order=0)
    opt_b = PollOption.objects.create(poll=poll, text="B", order=1)
    return poll, opt_a, opt_b


@pytest.fixture
def closed_poll(alice, community):
    post = Post.objects.create(author=alice, community=community, kind="poll", title="closed")
    poll = Poll.objects.create(post=post, closes_at=timezone.now() - timedelta(hours=1))
    opt = PollOption.objects.create(poll=poll, text="A", order=0)
    return poll, opt


@pytest.mark.django_db
class TestPollVote:
    def test_anonymous_rejected(self, api, open_poll):
        poll, opt_a, _ = open_poll
        assert (
            api.post(poll_vote_url(poll.id), {"option_id": opt_a.id}, format="json").status_code
            == 401
        )

    def test_vote_records(self, api, bob, open_poll):
        poll, opt_a, _ = open_poll
        api.force_authenticate(bob)
        resp = api.post(poll_vote_url(poll.id), {"option_id": opt_a.id}, format="json")
        assert resp.status_code == 201
        assert PollVote.objects.filter(poll=poll, user=bob, option=opt_a).exists()
        assert resp.data["total_votes"] == 1
        assert resp.data["user_option"] == opt_a.id

    def test_vote_can_be_changed(self, api, bob, open_poll):
        poll, opt_a, opt_b = open_poll
        api.force_authenticate(bob)
        api.post(poll_vote_url(poll.id), {"option_id": opt_a.id}, format="json")
        resp = api.post(poll_vote_url(poll.id), {"option_id": opt_b.id}, format="json")
        assert resp.status_code == 200
        assert PollVote.objects.filter(poll=poll, user=bob).count() == 1
        assert PollVote.objects.get(poll=poll, user=bob).option_id == opt_b.id

    def test_option_must_belong_to_poll(self, api, bob, open_poll, closed_poll):
        poll, _, _ = open_poll
        _, stray_opt = closed_poll
        api.force_authenticate(bob)
        resp = api.post(poll_vote_url(poll.id), {"option_id": stray_opt.id}, format="json")
        assert resp.status_code == 400

    def test_closed_poll_rejects_vote(self, api, bob, closed_poll):
        poll, opt = closed_poll
        api.force_authenticate(bob)
        resp = api.post(poll_vote_url(poll.id), {"option_id": opt.id}, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestPollDetail:
    def test_counts_and_percent(self, api, alice, bob, open_poll):
        poll, opt_a, opt_b = open_poll
        carol = User.objects.create_user(username="carol", email="c@x.com", password="x")
        PollVote.objects.create(poll=poll, option=opt_a, user=alice)
        PollVote.objects.create(poll=poll, option=opt_a, user=bob)
        PollVote.objects.create(poll=poll, option=opt_b, user=carol)
        resp = api.get(poll_detail_url(poll.id))
        assert resp.status_code == 200
        assert resp.data["total_votes"] == 3
        opts = {o["text"]: o for o in resp.data["options"]}
        assert opts["A"]["vote_count"] == 2
        assert opts["A"]["percent"] == pytest.approx(66.7, abs=0.1)
        assert opts["B"]["percent"] == pytest.approx(33.3, abs=0.1)

    def test_user_option_for_viewer(self, api, bob, open_poll):
        poll, opt_a, _ = open_poll
        PollVote.objects.create(poll=poll, option=opt_a, user=bob)
        api.force_authenticate(bob)
        resp = api.get(poll_detail_url(poll.id))
        assert resp.data["user_option"] == opt_a.id

    def test_is_closed_flag(self, api, closed_poll):
        poll, _ = closed_poll
        resp = api.get(poll_detail_url(poll.id))
        assert resp.data["is_closed"] is True
