from rest_framework.exceptions import APIException


class CannotFollowSelfError(APIException):
    status_code = 400
    default_code = "cannot_follow_self"
    default_detail = "You can't follow yourself."


class CannotRepostOwnError(APIException):
    status_code = 409
    default_code = "cannot_repost_own"
    default_detail = "You can't repost your own post."


class CannotRepostFalseError(APIException):
    status_code = 409
    default_code = "cannot_repost_false"
    default_detail = "Posts labelled FALSE can't be reposted."
