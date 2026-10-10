from rest_framework.exceptions import APIException


class CannotReportOwnError(APIException):
    status_code = 403
    default_code = "cannot_report_own"
    default_detail = "You can't report your own post."


class AlreadyReportedError(APIException):
    status_code = 409
    default_code = "already_reported"
    default_detail = "You already reported this post."
