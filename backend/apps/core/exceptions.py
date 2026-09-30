from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """DRF's handler, with a machine-readable `code` on every non-validation error.

    - validation errors keep {"field": ["message"]} (a bare list becomes non_field_errors)
    - everything else is {"detail": "...", "code": "..."}; throttling keeps its Retry-After header
    - unhandled exceptions return None, so Django produces its normal 500
    """
    # Same mapping DRF applies internally, done first so these get a `code` too.
    if isinstance(exc, Http404):
        exc = exceptions.NotFound(*exc.args)
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied(*exc.args)

    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, exceptions.ValidationError):
        if isinstance(response.data, list):
            response.data = {"non_field_errors": response.data}
        return response

    if isinstance(exc.detail, (list, dict)):
        return response
    response.data = {
        "detail": str(exc.detail),
        "code": getattr(exc.detail, "code", None) or exc.default_code,
    }
    return response
