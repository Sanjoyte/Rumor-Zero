import json

import pytest
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.core.exceptions import api_exception_handler


def call(exc, **view_attrs):
    """Run a view that raises `exc` and return (response, parsed JSON body)."""

    class RaisingView(APIView):
        authentication_classes = []
        permission_classes = []

        def get(self, request):
            raise exc

    for name, value in view_attrs.items():
        setattr(RaisingView, name, value)
    response = RaisingView.as_view()(APIRequestFactory().get("/"))
    response.render()
    return response, json.loads(response.content)


def test_not_found_has_a_code():
    response, body = call(exceptions.NotFound())
    assert response.status_code == 404
    assert body == {"detail": "Not found.", "code": "not_found"}


def test_django_http404_gets_the_same_shape():
    response, body = call(Http404())
    assert response.status_code == 404
    assert body["code"] == "not_found"


def test_django_permission_denied_gets_a_code():
    response, body = call(DjangoPermissionDenied())
    assert response.status_code == 403
    assert body["code"] == "permission_denied"


def test_custom_permission_code_is_kept():
    exc = exceptions.PermissionDenied("Verify your email first.", code="email_unverified")
    response, body = call(exc)
    assert response.status_code == 403
    assert body == {"detail": "Verify your email first.", "code": "email_unverified"}


def test_throttled_keeps_retry_after():
    response, body = call(exceptions.Throttled(wait=30))
    assert response.status_code == 429
    assert body["code"] == "throttled"
    assert response["Retry-After"] == "30"


def test_unauthenticated_is_a_401_with_a_code_when_an_authenticator_supplies_a_challenge():
    response, body = call(
        exceptions.NotAuthenticated(),
        authentication_classes=[BasicAuthentication],
        permission_classes=[IsAuthenticated],
    )
    assert response.status_code == 401
    assert body["code"] == "not_authenticated"
    assert "WWW-Authenticate" in response


def test_field_validation_errors_are_unchanged():
    response, body = call(exceptions.ValidationError({"email": ["Enter a valid email address."]}))
    assert response.status_code == 400
    assert body == {"email": ["Enter a valid email address."]}


@pytest.mark.parametrize("detail", [["Not allowed."], "Not allowed."])
def test_bare_validation_errors_become_non_field_errors(detail):
    response, body = call(exceptions.ValidationError(detail))
    assert response.status_code == 400
    assert body == {"non_field_errors": ["Not allowed."]}


def test_unhandled_exceptions_are_left_to_django():
    assert api_exception_handler(RuntimeError("boom"), {}) is None
