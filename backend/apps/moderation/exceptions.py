"""API errors for appeals. `APIException`s, so the core handler shapes them as
`{"detail", "code"}` (a validation error would carry no code). A missing post is DRF's `NotFound`
and someone else's post is `posts.exceptions.NotAuthorError` (403 `not_author`)."""

from rest_framework.exceptions import APIException


class AlreadyAppealedError(APIException):
    status_code = 409
    default_code = "already_appealed"
    default_detail = "You already asked for another look at this post."


class NotAppealableError(APIException):
    status_code = 409
    default_code = "not_appealable"
    default_detail = "Only posts labelled FALSE or removed can be appealed."
