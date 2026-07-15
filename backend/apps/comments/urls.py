from django.urls import path

from .views import CommentDetailView, CommentRevisionListView, PostCommentListCreateView

post_comments_urlpatterns = [
    path(
        "posts/<int:pk>/comments/",
        PostCommentListCreateView.as_view(),
        name="post-comments",
    ),
]

comments_urlpatterns = [
    path("comments/<int:pk>/", CommentDetailView.as_view(), name="comment-detail"),
    path(
        "comments/<int:pk>/revisions/",
        CommentRevisionListView.as_view(),
        name="comment-revisions",
    ),
]
