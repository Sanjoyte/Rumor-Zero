"""GET|HEAD /api/v1/avatars/{user_id}/{version}-{size}.webp (ARCHITECTURE §4e): the one place photo
bytes leave the database."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts import avatars
from apps.accounts.models import Avatar, User
from apps.accounts.tests import photo_fixtures as fx
from apps.accounts.tests.conftest import access_token_for
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

HEADERS = {
    "Content-Type": "image/webp",
    "Cache-Control": "public, max-age=31536000, immutable",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
    "Content-Disposition": 'inline; filename="avatar.webp"',
}


@pytest.fixture
def owner():
    user = UserFactory(is_email_verified=True)
    fx.give_photo(user, fx.gps_jpeg())
    return user


def url_for(user, size=256, version=None):
    version = version or Avatar.objects.get(user=user).version
    return f"/api/v1/avatars/{user.pk}/{version}-{size}.webp"


def assert_headers(response, user, size):
    for name, value in HEADERS.items():
        assert response[name] == value, name
    version = Avatar.objects.get(user=user).version
    assert response["ETag"] == f'"{version}-{size}"'


# ---------- 200 ----------


@pytest.mark.parametrize(("size", "column"), [(256, "image_256"), (96, "image_96")])
def test_each_size_is_served_with_the_immutable_nosniff_sandbox_headers(
    api_client, owner, size, column
):
    response = api_client.get(url_for(owner, size))

    assert response.status_code == 200
    assert_headers(response, owner, size)
    assert response.content == bytes(getattr(Avatar.objects.get(user=owner), column))
    assert fx.decode(response.content).size == (size, size)
    assert fx.riff_chunks(response.content) == ["VP8 "]


def test_nosniff_is_set_by_the_view_not_only_by_the_security_middleware(settings, owner):
    """Django's SecurityMiddleware adds it too; a settings change must not remove it from photos."""
    from rest_framework.test import APIClient

    settings.SECURE_CONTENT_TYPE_NOSNIFF = False
    response = APIClient().get(url_for(owner))
    assert response["X-Content-Type-Options"] == "nosniff"
    other = APIClient().get("/api/health/")
    assert "X-Content-Type-Options" not in other  # the setting really was off


def test_only_webp_is_ever_served_whatever_was_uploaded(api_client):
    for upload in (fx.gps_jpeg(), fx.png(), fx.mpo()):
        user = UserFactory(is_email_verified=True)
        fx.give_photo(user, upload)
        for size in (96, 256):
            body = api_client.get(url_for(user, size)).content
            assert body[:4] == b"RIFF" and body[8:12] == b"WEBP"


def test_a_serve_is_one_query_and_no_cookie_or_vary_on_cookie(api_client, owner):
    url = url_for(owner)
    with CaptureQueriesContext(connection) as queries:
        response = api_client.get(url)
    assert len(queries) == 1
    assert "Set-Cookie" not in response
    assert "cookie" not in response.get("Vary", "").lower()


def test_head_answers_the_same_headers_with_no_body(api_client, owner):
    response = api_client.head(url_for(owner, 96))
    assert response.status_code == 200
    assert_headers(response, owner, 96)
    assert response.content == b""


def test_a_stale_or_garbage_token_does_not_turn_a_public_image_into_a_401(api_client, owner):
    for token in ("garbage", access_token_for(UserFactory())[:-3] + "xyz"):
        assert (
            api_client.get(url_for(owner), HTTP_AUTHORIZATION=f"Bearer {token}").status_code == 200
        )


def test_it_is_public_and_never_throttled(api_client, owner):
    url = url_for(owner)
    assert all(api_client.get(url).status_code == 200 for _ in range(40))


# ---------- 304 ----------


def test_a_repeat_request_with_the_etag_is_a_304_without_loading_the_bytes(api_client, owner):
    url = url_for(owner)
    etag = api_client.get(url)["ETag"]

    with CaptureQueriesContext(connection) as queries:
        response = api_client.get(url, HTTP_IF_NONE_MATCH=etag)

    assert response.status_code == 304
    assert response.content == b""
    assert_headers_without_type(response, owner, 256)
    assert len(queries) == 1
    assert "image_" not in queries[0]["sql"]


def assert_headers_without_type(response, owner, size):
    """A 304 has no Content-Type (Django removes it) but keeps the caching headers."""
    for name, value in HEADERS.items():
        if name != "Content-Type":
            assert response[name] == value, name
    assert response["ETag"] == f'"{Avatar.objects.get(user=owner).version}-{size}"'


@pytest.mark.parametrize(
    "header",
    ['"{etag}"', 'W/"{etag}"', '"other", "{etag}"', "*"],
    ids=["strong", "weak", "in-a-list", "star"],
)
def test_if_none_match_is_understood_in_every_form(api_client, owner, header):
    etag = f"{Avatar.objects.get(user=owner).version}-256"
    response = api_client.get(url_for(owner), HTTP_IF_NONE_MATCH=header.format(etag=etag))
    assert response.status_code == 304


def test_another_etag_gets_the_full_image(api_client, owner):
    response = api_client.get(url_for(owner), HTTP_IF_NONE_MATCH='"0123456789abcdef-256"')
    assert response.status_code == 200 and response.content


def test_the_etag_of_the_other_size_is_not_a_match(api_client, owner):
    version = Avatar.objects.get(user=owner).version
    response = api_client.get(url_for(owner, 256), HTTP_IF_NONE_MATCH=f'"{version}-96"')
    assert response.status_code == 200


def test_a_304_still_checks_the_version_a_wrong_one_is_404_not_304(api_client, owner):
    wrong = url_for(owner, 256, version="0123456789abcdef")
    for header in ('"0123456789abcdef-256"', "*"):
        response = api_client.get(wrong, HTTP_IF_NONE_MATCH=header)
        assert response.status_code == 404, header


def test_a_304_for_another_users_photo_is_404(api_client, owner):
    other = UserFactory()
    version = Avatar.objects.get(user=owner).version
    url = f"/api/v1/avatars/{other.pk}/{version}-256.webp"
    assert api_client.get(url, HTTP_IF_NONE_MATCH=f'"{version}-256"').status_code == 404


# ---------- 404 ----------


def assert_not_found(response):
    assert response.status_code == 404
    assert response.json() == {"detail": "Not found.", "code": "not_found"}
    assert "immutable" not in response.get("Cache-Control", "")


def test_a_wrong_version_is_404(api_client, owner):
    assert_not_found(api_client.get(url_for(owner, 256, version="0123456789abcdef")))


@pytest.mark.parametrize("size", [0, 64, 97, 128, 255, 257, 512, 1024])
def test_only_the_two_sizes_exist(api_client, owner, size):
    version = Avatar.objects.get(user=owner).version
    assert_not_found(api_client.get(f"/api/v1/avatars/{owner.pk}/{version}-{size}.webp"))


@pytest.mark.parametrize(
    "name",
    [
        "{v}-256.png",
        "{v}-256.WEBP",
        "{v}-256.webp.",
        "{v}-256",
        "{v}256.webp",
        "{V}-256.webp",
        "{v}00-256.webp",
        "{short}-256.webp",
        "{v}-256.webp%00",
        "-256.webp",
        "avatar.webp",
    ],
)
def test_any_other_name_is_404(api_client, owner, name):
    version = Avatar.objects.get(user=owner).version
    name = name.format(v=version, V=version.upper(), short=version[:15])
    assert_not_found(api_client.get(f"/api/v1/avatars/{owner.pk}/{name}"))


def test_a_name_with_a_slash_never_reaches_the_view(api_client, owner):
    """`<str:name>` doesn't match "/", so Django's own 404 answers (not our JSON one)."""
    version = Avatar.objects.get(user=owner).version
    for name in (f"{version}-256.webp/", f"../{version}-256.webp", f"..%2F{version}-256.webp"):
        assert api_client.get(f"/api/v1/avatars/{owner.pk}/{name}").status_code == 404


def test_an_unknown_account_or_a_malformed_id_is_404(api_client, owner):
    version = Avatar.objects.get(user=owner).version
    name = f"{version}-256.webp"
    for bad in (
        "00000000-0000-0000-0000-000000000000",
        "not-a-uuid",
        "1",
        str(owner.pk).upper(),  # one address per image: only the canonical spelling
        "{" + str(owner.pk) + "}",
        str(owner.pk).replace("-", ""),
        "urn:uuid:" + str(owner.pk),
        str(owner.pk) + "%00",
    ):
        assert_not_found(api_client.get(f"/api/v1/avatars/{bad}/{name}"))


def test_someone_elses_version_does_not_work_on_my_id(api_client, owner):
    other = UserFactory(is_email_verified=True)
    fx.give_photo(other, fx.jpeg(colour=fx.BLUE))
    mine = Avatar.objects.get(user=owner).version
    theirs = Avatar.objects.get(user=other).version
    assert_not_found(api_client.get(f"/api/v1/avatars/{owner.pk}/{theirs}-256.webp"))
    assert_not_found(api_client.get(f"/api/v1/avatars/{other.pk}/{mine}-256.webp"))


def test_a_changed_photo_changes_the_url_and_the_old_one_is_404(api_client, owner):
    old = url_for(owner)
    avatars.save_photo(owner.pk, fx.jpeg(colour=fx.BLUE))
    assert_not_found(api_client.get(old))
    assert_not_found(api_client.get(old.replace("-256", "-96")))
    assert api_client.get(url_for(owner)).status_code == 200
    # ... and a client that cached the old one gets 404, not a 304, when it asks again.
    etag = f'"{old.rsplit("/", 1)[1].removesuffix(".webp")}"'
    assert api_client.get(old, HTTP_IF_NONE_MATCH=etag).status_code == 404


def test_a_removed_photo_is_404_at_once(api_client, owner):
    url = url_for(owner)
    assert api_client.get(url).status_code == 200
    avatars.delete_photo(owner.pk)
    assert_not_found(api_client.get(url))


def test_a_deleted_account_takes_its_photo_with_it(api_client, owner):
    url = url_for(owner)
    User.objects.filter(pk=owner.pk).delete()
    assert_not_found(api_client.get(url))
    assert not Avatar.objects.exists()


def test_only_get_and_head_are_allowed(api_client, owner):
    url = url_for(owner)
    for method in ("post", "put", "patch", "delete"):
        response = getattr(api_client, method)(
            url, HTTP_AUTHORIZATION=f"Bearer {access_token_for(owner)}"
        )
        assert response.status_code == 405, method
