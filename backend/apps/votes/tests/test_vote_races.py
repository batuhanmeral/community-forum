import threading
import time

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connections
from django.db.models import Sum
from django.db.models.signals import pre_delete, pre_save
from django.urls import reverse
from rest_framework.test import APIClient

from apps.communities.models import Community
from apps.posts.models import Post
from apps.votes.models import Vote

User = get_user_model()
VOTE_URL = reverse("api_v1:votes:vote")
OK_STATUSES = {200, 201, 204}
READ_TO_DELETE_DELAY = 0.3


@pytest.mark.django_db(transaction=True)
def test_concurrent_toggle_off_keeps_karma_consistent():
    alice = User.objects.create_user(username="alice", email="a@x.com", password="x")
    bob = User.objects.create_user(username="bob", email="b@x.com", password="x")
    community = Community.objects.create(slug="python", name="Python", creator=alice)
    post = Post.objects.create(author=alice, community=community, kind="text", title="t")
    Vote.objects.create(
        user=bob, content_type=ContentType.objects.get_for_model(Post), object_id=post.id, value=1
    )

    barrier = threading.Barrier(2)
    statuses, errors = [], []

    def toggle():
        try:
            barrier.wait(timeout=10)
            client = APIClient()
            client.force_authenticate(bob)
            payload = {"content_type": "post", "object_id": post.id, "value": 1}
            statuses.append(client.post(VOTE_URL, payload, format="json").status_code)
        except Exception as exc:  # surfaced by the assertion below
            errors.append(exc)
        finally:
            connections.close_all()

    def slow_delete(sender, **kwargs):
        # Widens the window so both requests read the vote before either deletes it.
        time.sleep(READ_TO_DELETE_DELAY)

    pre_delete.connect(slow_delete, sender=Vote)
    try:
        threads = [threading.Thread(target=toggle) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
    finally:
        pre_delete.disconnect(slow_delete, sender=Vote)

    assert errors == []
    assert len(statuses) == 2
    assert set(statuses) <= OK_STATUSES
    alice.refresh_from_db()
    vote_sum = Vote.objects.filter(object_id=post.id).aggregate(s=Sum("value"))["s"] or 0
    assert alice.post_karma == vote_sum


@pytest.mark.django_db(transaction=True)
def test_mutual_votes_do_not_deadlock():
    alice = User.objects.create_user(username="alice", email="a@x.com", password="x")
    bob = User.objects.create_user(username="bob", email="b@x.com", password="x")
    community = Community.objects.create(slug="python", name="Python", creator=alice)
    alice_post = Post.objects.create(author=alice, community=community, kind="text", title="a")
    bob_post = Post.objects.create(author=bob, community=community, kind="text", title="b")

    barrier = threading.Barrier(2)
    statuses, errors = [], []

    def vote(voter, target):
        try:
            barrier.wait(timeout=10)
            client = APIClient()
            client.force_authenticate(voter)
            payload = {"content_type": "post", "object_id": target.id, "value": 1}
            statuses.append(client.post(VOTE_URL, payload, format="json").status_code)
        except Exception as exc:  # surfaced by the assertion below
            errors.append(exc)
        finally:
            connections.close_all()

    def slow_save(sender, **kwargs):
        # Both transactions hold their voter lock before either reaches the karma UPDATE.
        time.sleep(READ_TO_DELETE_DELAY)

    pre_save.connect(slow_save, sender=Vote)
    try:
        threads = [
            threading.Thread(target=vote, args=(alice, bob_post)),
            threading.Thread(target=vote, args=(bob, alice_post)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
    finally:
        pre_save.disconnect(slow_save, sender=Vote)

    assert errors == []
    assert statuses == [201, 201]
    alice.refresh_from_db()
    bob.refresh_from_db()
    assert (alice.post_karma, bob.post_karma) == (1, 1)
