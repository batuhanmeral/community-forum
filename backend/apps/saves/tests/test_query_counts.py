import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework.test import APIClient

from apps.comments.models import Comment
from apps.communities.models import Community
from apps.posts.models import Post
from apps.saves.models import SavedItem

User = get_user_model()

SAVED = reverse("api_v1:saves:saved-list")


@pytest.mark.django_db
def test_ten_saved_posts_and_comments_within_eight_queries(django_assert_max_num_queries):
    me = User.objects.create_user(username="me", email="me@x.com", password="x")
    community = Community.objects.create(slug="py", name="Python", creator=me)
    post_ct = ContentType.objects.get_for_model(Post)
    comment_ct = ContentType.objects.get_for_model(Comment)
    for i in range(5):
        author = User.objects.create_user(username=f"a{i}", email=f"a{i}@x.com", password="x")
        post = Post.objects.create(author=author, community=community, kind="text", title=f"p{i}")
        comment = Comment.objects.create(post=post, author=author, body="c")
        SavedItem.objects.create(user=me, content_type=post_ct, object_id=post.pk)
        SavedItem.objects.create(user=me, content_type=comment_ct, object_id=comment.pk)
    client = APIClient()
    client.force_authenticate(me)
    with django_assert_max_num_queries(8):
        resp = client.get(SAVED)
    assert len(resp.data["results"]) == 10
