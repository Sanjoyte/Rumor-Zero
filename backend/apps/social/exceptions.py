from rest_framework.exceptions import APIException


class CannotFollowSelfError(APIException):
    status_code = 400
    default_code = "cannot_follow_self"
    default_detail = "You can't follow yourself."
