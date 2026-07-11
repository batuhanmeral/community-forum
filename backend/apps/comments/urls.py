from django.urls import path

from .views import CommentDetailView, PostCommentListCreateView

post_comments_urlpatterns = [
    path(
        "posts/<int:pk>/comments/",
        PostCommentListCreateView.as_view(),
        name="post-comments",
    ),
]

comments_urlpatterns = [
    path("comments/<int:pk>/", CommentDetailView.as_view(), name="comment-detail"),
]
