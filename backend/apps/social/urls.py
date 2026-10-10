from django.urls import path

from apps.social import views

urlpatterns = [
    path("v1/feed/", views.FeedView.as_view(), name="feed"),
    path("v1/users/<str:username>/", views.ProfileView.as_view(), name="profile"),
    path("v1/users/<str:username>/posts/", views.UserPostsView.as_view(), name="profile-posts"),
    path("v1/users/<str:username>/followers/", views.FollowersView.as_view(), name="followers"),
    path("v1/users/<str:username>/following/", views.FollowingView.as_view(), name="following"),
    path("v1/users/<str:username>/follow/", views.FollowView.as_view(), name="follow"),
    path("v1/posts/<str:post_id>/like/", views.LikeView.as_view(), name="like"),
    path("v1/posts/<str:post_id>/comments/", views.CommentListView.as_view(), name="comments"),
    path("v1/comments/<str:comment_id>/", views.CommentDetailView.as_view(), name="comment"),
]
