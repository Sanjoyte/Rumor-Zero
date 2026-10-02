"""IsEmailVerified: unverified accounts are read-only (ARCHITECTURE §7)."""

import pytest
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.accounts.permissions import IsEmailVerified
from apps.accounts.tests.conftest import access_token_for
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class VerifiedOnlyView(APIView):
    """A test-only stand-in for the write endpoints of Parts 4–14."""

    permission_classes = [IsAuthenticated, IsEmailVerified]

    def post(self, request):
        return Response({"ok": True}, status=201)


def call(user=None):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {access_token_for(user)}"} if user else {}
    request = APIRequestFactory().post("/verified-only/", {}, format="json", **headers)
    return VerifiedOnlyView.as_view()(request)


def test_an_unverified_user_gets_403_email_unverified():
    response = call(UserFactory(is_email_verified=False))
    assert response.status_code == 403
    assert response.data["code"] == "email_unverified"
    assert response.data["detail"] == IsEmailVerified.message


def test_a_verified_user_passes():
    assert call(UserFactory(is_email_verified=True)).status_code == 201


def test_anonymous_gets_401_not_403():
    response = call()
    assert response.status_code == 401
    assert response.data["code"] == "not_authenticated"


def test_the_permission_alone_still_answers_anonymous_with_401():
    class OnlyVerified(VerifiedOnlyView):
        permission_classes = [IsEmailVerified]

    request = APIRequestFactory().post("/verified-only/", {}, format="json")
    assert OnlyVerified.as_view()(request).status_code == 401
