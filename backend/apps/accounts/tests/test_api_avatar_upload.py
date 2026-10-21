"""PUT /api/v1/me/avatar/ (ARCHITECTURE §4e, §9): permissions, the throttle, refusals, what is
stored, and the decode gate."""

import threading
import time

import pytest
from django.core.files.uploadhandler import (
    StopFutureHandlers,
    StopUpload,
    TemporaryFileUploadHandler,
)
from django.db import connection
from django.test.client import FakePayload
from django.utils import timezone

from apps.accounts import avatars
from apps.accounts.models import Avatar, User
from apps.accounts.tests import photo_fixtures as fx
from apps.accounts.tests.conftest import access_token_for, run_together
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/me/avatar/"
ME_KEYS = {
    "id",
    "username",
    "display_name",
    "bio",
    "email",
    "is_email_verified",
    "role",
    "has_usable_password",
    "google_connected",
    "avatar_url",
    "avatar_uploads_blocked",
    "public_score",
}


def verified(**kwargs):
    return UserFactory(is_email_verified=True, **kwargs)


def put(client, user, data=None, *, name="photo.jpg", content_type="image/jpeg", field="file"):
    payload = {} if data is None else {field: fx.upload(data, name, content_type)}
    return client.put(
        URL,
        payload,
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {access_token_for(user)}",
    )


def code_of(response):
    return response.json()["code"]


# ---------- A photo is saved ----------


def test_a_verified_user_sets_a_photo_and_gets_their_me_object_back(api_client):
    user = verified()
    response = put(api_client, user, fx.gps_jpeg())

    assert response.status_code == 200
    data = response.json()
    assert set(data) == ME_KEYS
    row = Avatar.objects.get(user=user)
    assert data["avatar_url"] == f"/api/v1/avatars/{user.pk}/{row.version}-256.webp"
    assert data["avatar_uploads_blocked"] is False
    user.refresh_from_db()
    assert user.avatar_version == row.version
    assert "no-cache" in response["Cache-Control"]


def test_the_row_holds_the_two_webp_sizes_and_their_total(api_client):
    user = verified()
    put(api_client, user, fx.gps_jpeg())

    row = Avatar.objects.get(user=user)
    assert fx.riff_chunks(bytes(row.image_256)) == ["VP8 "]
    assert fx.decode(bytes(row.image_256)).size == (256, 256)
    assert fx.decode(bytes(row.image_96)).size == (96, 96)
    assert row.bytes_total == len(bytes(row.image_256)) + len(bytes(row.image_96))
    assert len(row.version) == 16


def test_there_is_no_column_that_could_hold_the_original():
    assert {f.name for f in Avatar._meta.get_fields()} == {
        "user",
        "image_256",
        "image_96",
        "version",
        "bytes_total",
        "created_at",
        "updated_at",
    }


def test_the_original_never_touches_the_disk(api_client, settings, tmp_path, monkeypatch):
    settings.FILE_UPLOAD_TEMP_DIR = tmp_path
    big = fx.noisy_jpeg()
    assert 2.5 * 1024 * 1024 < len(big) < avatars.MAX_UPLOAD_BYTES  # Django would spool it

    def forbidden(*args, **kwargs):
        raise AssertionError("an upload handler that can write a temp file was used")

    monkeypatch.setattr(TemporaryFileUploadHandler, "__init__", forbidden)
    monkeypatch.setattr(TemporaryFileUploadHandler, "new_file", forbidden)
    user = verified()
    response = put(api_client, user, big)

    assert response.status_code == 200
    assert list(tmp_path.iterdir()) == []


def test_the_extension_and_the_declared_type_are_never_trusted(api_client):
    user = verified()
    png = put(api_client, user, fx.png(), name="x.jpg", content_type="image/jpeg")
    jpeg = put(api_client, user, fx.jpeg(), name="x.png", content_type="image/gif")
    assert (png.status_code, jpeg.status_code) == (200, 200)
    svg = put(api_client, user, fx.SVG, name="x.jpg", content_type="image/jpeg")
    assert (svg.status_code, code_of(svg)) == (400, "photo_unsupported")


def test_a_new_photo_has_a_new_version_and_the_same_photo_the_same_one(api_client):
    user = verified()
    first = put(api_client, user, fx.jpeg(colour=fx.RED)).json()["avatar_url"]
    again = put(api_client, user, fx.jpeg(colour=fx.RED)).json()["avatar_url"]
    other = put(api_client, user, fx.jpeg(colour=fx.BLUE)).json()["avatar_url"]

    assert first == again
    assert other != first
    assert Avatar.objects.filter(user=user).count() == 1
    user.refresh_from_db()
    assert other.endswith(f"/{user.avatar_version}-256.webp")


def test_replacing_a_photo_keeps_when_it_was_first_set(api_client):
    user = verified()
    put(api_client, user, fx.jpeg(colour=fx.RED))
    first = Avatar.objects.get(user=user)
    put(api_client, user, fx.jpeg(colour=fx.BLUE))
    second = Avatar.objects.get(user=user)

    assert second.created_at == first.created_at
    assert second.updated_at >= first.updated_at
    assert second.version != first.version


def test_one_user_never_changes_another_users_photo(api_client):
    ada, bo = verified(), verified()
    fx.give_photo(bo, fx.jpeg(colour=fx.GREEN))
    before = Avatar.objects.get(user=bo).version
    put(api_client, ada, fx.jpeg(colour=fx.RED))

    assert Avatar.objects.get(user=bo).version == before
    assert Avatar.objects.count() == 2


# ---------- Who may upload ----------


def test_anonymous_gets_401(api_client):
    response = api_client.put(URL, {"file": fx.upload(fx.jpeg())}, format="multipart")
    assert response.status_code == 401
    assert not Avatar.objects.exists()


def test_an_unverified_email_gets_403_email_unverified_and_it_never_counts(api_client):
    user = UserFactory()
    for _ in range(7):  # more than the 5 a day: a permission refusal isn't an attempt
        response = put(api_client, user, fx.jpeg())
        assert response.status_code == 403 and code_of(response) == "email_unverified"
    assert not Avatar.objects.exists()

    User.objects.filter(pk=user.pk).update(is_email_verified=True)
    assert put(api_client, user, fx.jpeg()).status_code == 200


def test_blocked_uploads_get_403_photo_uploads_blocked_and_it_never_counts(api_client):
    user = verified(avatar_uploads_blocked=True)
    for _ in range(7):
        response = put(api_client, user, fx.jpeg())
        assert response.status_code == 403
        assert response.json() == {
            "detail": "A moderator turned off photo uploads for your account.",
            "code": "photo_uploads_blocked",
        }
    assert not Avatar.objects.exists()

    User.objects.filter(pk=user.pk).update(avatar_uploads_blocked=False)
    assert put(api_client, user, fx.jpeg()).status_code == 200


def test_unverified_comes_before_blocked(api_client):
    user = UserFactory(avatar_uploads_blocked=True)
    assert code_of(put(api_client, user, fx.jpeg())) == "email_unverified"


# ---------- The throttle: 5 a day, PUT only, refused photos count ----------


def test_the_sixth_upload_of_a_day_is_429(api_client):
    user = verified()
    for index in range(5):
        assert put(api_client, user, fx.jpeg(colour=(index * 40, 10, 10))).status_code == 200
    sixth = put(api_client, user, fx.jpeg())
    assert sixth.status_code == 429 and code_of(sixth) == "throttled"


def test_a_refused_photo_counts_against_the_five(api_client):
    user = verified()
    for _ in range(5):
        assert put(api_client, user, fx.SVG).status_code == 400
    assert put(api_client, user, fx.jpeg()).status_code == 429


def test_the_allowance_is_per_person(api_client):
    ada, bo = verified(), verified()
    for _ in range(5):
        put(api_client, ada, fx.SVG)
    assert put(api_client, ada, fx.jpeg()).status_code == 429
    assert put(api_client, bo, fx.jpeg()).status_code == 200


def test_taking_a_photo_down_neither_counts_nor_waits_for_the_allowance(api_client):
    user = verified()
    for _ in range(5):
        put(api_client, user, fx.SVG)
    assert put(api_client, user, fx.jpeg()).status_code == 429
    response = api_client.delete(URL, HTTP_AUTHORIZATION=f"Bearer {access_token_for(user)}")
    assert response.status_code == 204


# ---------- Refusals ----------


def test_no_file_is_400_photo_missing(api_client):
    user = verified()
    assert code_of(put(api_client, user)) == "photo_missing"
    # A different field name, or a plain text field called "file", is no file either.
    assert code_of(put(api_client, user, fx.jpeg(), field="photo")) == "photo_missing"
    text = api_client.put(
        URL,
        {"file": "not a file"},
        format="multipart",
        HTTP_AUTHORIZATION=f"Bearer {access_token_for(user)}",
    )
    assert (text.status_code, code_of(text)) == (400, "photo_missing")


def test_only_multipart_is_accepted(api_client):
    user = verified()
    response = api_client.put(
        URL, {"file": "x"}, format="json", HTTP_AUTHORIZATION=f"Bearer {access_token_for(user)}"
    )
    assert response.status_code == 415


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (fx.SVG, "photo_unsupported"),
        (fx.gif(), "photo_unsupported"),
        (fx.HEIC, "photo_unsupported"),
        (fx.apng(), "photo_unsupported"),
        (fx.png(100, 100), "photo_too_small"),
        (fx.flat_png(8000, 8000), "photo_too_many_pixels"),
        (fx.flat_png(5001, 5000), "photo_too_many_pixels"),
    ],
    ids=["svg", "gif", "heic", "animated-png", "small", "bomb-64mp", "bomb-25mp+"],
)
def test_an_unusable_photo_is_a_400_with_a_code_and_changes_nothing(api_client, data, code):
    user = verified()
    response = put(api_client, user, data)

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == code and body["detail"] == avatars.MESSAGES[code]
    assert not Avatar.objects.exists()
    user.refresh_from_db()
    assert user.avatar_version is None


def test_a_refused_photo_leaves_the_old_one_in_place(api_client):
    user = verified()
    version = fx.give_photo(user)
    assert put(api_client, user, fx.SVG).status_code == 400
    user.refresh_from_db()
    assert user.avatar_version == version == Avatar.objects.get(user=user).version


# ---------- The size limit is enforced while reading, not afterwards ----------


class CountingPayload(FakePayload):
    """A request body that counts the bytes the server actually reads from it."""

    def __init__(self, data):
        super().__init__(data)
        self.read_bytes = 0

    def read(self, size=-1):
        chunk = super().read(size)
        self.read_bytes += len(chunk)
        return chunk


def raw_put(client, user, body, content_type, *, declared=None):
    """A PUT whose body is `body` and whose Content-Length is `declared` (default: its length)."""
    payload = CountingPayload(body)
    response = client.generic(
        "PUT",
        URL,
        data=b"",
        content_type=content_type,
        CONTENT_LENGTH=str(len(body) if declared is None else declared),
        HTTP_AUTHORIZATION=f"Bearer {access_token_for(user)}",
        **{"wsgi.input": payload},
    )
    return response, payload


def multipart(file_bytes):
    from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart

    body = encode_multipart(BOUNDARY, {"file": fx.upload(file_bytes)})
    return body, MULTIPART_CONTENT


def test_a_body_that_declares_more_than_it_may_is_refused_before_a_byte_is_read(api_client):
    user = verified()
    body, content_type = multipart(b"\xff\xd8" + b"0" * (avatars.MAX_BODY_BYTES + 10))
    response, payload = raw_put(api_client, user, body, content_type)

    assert response.status_code == 400 and code_of(response) == "photo_too_large"
    assert payload.read_bytes == 0


def test_a_file_one_byte_over_5_mb_is_refused_and_the_read_stops_at_the_cap(api_client):
    user = verified()
    body, content_type = multipart(b"\xff\xd8" + b"0" * (avatars.MAX_UPLOAD_BYTES - 1))
    assert len(body) <= avatars.MAX_BODY_BYTES  # it passes the declared-length check
    response, payload = raw_put(api_client, user, body, content_type)

    assert response.status_code == 400 and code_of(response) == "photo_too_large"
    assert payload.read_bytes <= avatars.MAX_BODY_BYTES


def test_a_body_that_lies_about_its_length_is_cut_off(api_client):
    """Declares 1 KB, sends 8 MB: only what was declared is ever read."""
    user = verified()
    body, content_type = multipart(b"\xff\xd8" + b"0" * (8 * 1024 * 1024))
    response, payload = raw_put(api_client, user, body, content_type, declared=1024)

    assert response.status_code == 400
    assert payload.read_bytes <= 1024


def test_exactly_5_mb_of_file_is_accepted_by_the_reader(api_client):
    """A real JPEG padded to exactly 5 MB (trailing bytes are ignored by the decoder)."""
    user = verified()
    jpeg = fx.jpeg()
    padded = jpeg + b"\x00" * (avatars.MAX_UPLOAD_BYTES - len(jpeg))
    assert put(api_client, user, padded).status_code == 200


class TestUploadHandler:
    """`PhotoUploadHandler` on its own. Through the API the declared-length check already bounds
    the body, so the cap that cuts off a lying body is only visible here."""

    @staticmethod
    def started():
        handler = avatars.PhotoUploadHandler()
        handler.handle_raw_input(
            None, {}, 10**9, b"boundary"
        )  # Django would switch off over 2.5 MB
        return handler

    def feed(self, handler, total, chunk=64 * 1024):
        for start in range(0, total, chunk):
            handler.receive_data_chunk(b"x" * min(chunk, total - start), start)

    def test_it_stays_in_memory_whatever_the_declared_length(self):
        handler = self.started()
        assert handler.activated is True
        with pytest.raises(StopFutureHandlers):
            handler.new_file("file", "a.jpg", "image/jpeg", 10**9)
        self.feed(handler, 3 * 1024 * 1024)
        upload = handler.file_complete(3 * 1024 * 1024)
        assert upload.__class__.__name__ == "InMemoryUploadedFile"
        assert upload.size == 3 * 1024 * 1024

    def test_exactly_5_mb_is_taken_and_one_byte_more_stops_the_upload(self):
        handler = self.started()
        with pytest.raises(StopFutureHandlers):
            handler.new_file("file", "a.jpg", "image/jpeg", 0)
        self.feed(handler, avatars.MAX_UPLOAD_BYTES)
        assert handler.too_large is False
        with pytest.raises(StopUpload) as stop:
            handler.receive_data_chunk(b"x", avatars.MAX_UPLOAD_BYTES)
        assert handler.too_large is True
        # The parser reads the rest of a body of a declared, bounded length; it doesn't reset.
        assert stop.value.connection_reset is False

    def test_the_cap_counts_every_file_of_the_request_together(self):
        handler = self.started()
        for name in ("a.jpg", "b.jpg"):
            with pytest.raises(StopFutureHandlers):
                handler.new_file("file", name, "image/jpeg", 0)
            half = avatars.MAX_UPLOAD_BYTES // 2 + 1
            try:
                self.feed(handler, half)
            except StopUpload:
                assert name == "b.jpg"
        assert handler.too_large is True


# ---------- Checked again under the account's lock ----------


def test_a_block_that_lands_while_the_photo_is_processed_wins(api_client, monkeypatch):
    user = verified()
    real = avatars.process_photo

    def block_meanwhile(data):
        photo = real(data)
        User.objects.filter(pk=user.pk).update(avatar_uploads_blocked=True)
        return photo

    monkeypatch.setattr(avatars, "process_photo", block_meanwhile)
    response = put(api_client, user, fx.jpeg())

    assert response.status_code == 403 and code_of(response) == "photo_uploads_blocked"
    assert not Avatar.objects.exists()
    user.refresh_from_db()
    assert user.avatar_version is None


def test_an_account_suspended_or_deleted_meanwhile_gets_no_photo(api_client, monkeypatch):
    real = avatars.process_photo
    for change in (
        lambda pk: User.objects.filter(pk=pk).update(is_active=False),
        lambda pk: User.objects.filter(pk=pk).delete(),
    ):
        user = verified()

        def run(data, pk=user.pk, change=change):
            photo = real(data)
            change(pk)
            return photo

        monkeypatch.setattr(avatars, "process_photo", run)
        response = put(api_client, user, fx.jpeg())
        assert response.status_code == 401
        assert not Avatar.objects.filter(user_id=user.pk).exists()


def test_saving_a_photo_never_touches_a_post(api_client):
    from django.test.utils import CaptureQueriesContext

    user = verified()
    with CaptureQueriesContext(connection) as queries:
        assert put(api_client, user, fx.jpeg()).status_code == 200
    assert not [q for q in queries if "posts_post" in q["sql"]]


# ---------- The decode gate: one decode at a time, site-wide ----------


@pytest.mark.django_db(transaction=True)
def test_a_busy_gate_is_503_photo_busy_with_retry_after_and_writes_nothing(api_client, monkeypatch):
    monkeypatch.setattr(avatars, "GATE_TIMEOUT", "300ms")
    user = verified()
    holding, release = threading.Event(), threading.Event()

    def hold_the_gate():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [avatars.GATE_KEY])
            holding.set()
            release.wait(timeout=20)
            cursor.execute("SELECT pg_advisory_unlock(%s)", [avatars.GATE_KEY])
        connection.close()

    holder = threading.Thread(target=hold_the_gate)
    holder.start()
    try:
        assert holding.wait(timeout=10)
        started = time.monotonic()
        response = put(api_client, user, fx.jpeg())
        waited = time.monotonic() - started
    finally:
        release.set()
        holder.join(timeout=20)

    assert response.status_code == 503 and code_of(response) == "photo_busy"
    assert response["Retry-After"] == str(avatars.BUSY_RETRY_SECONDS)
    assert 0.25 < waited < 5
    assert not Avatar.objects.exists()
    # The gate belongs to the transaction: once the holder lets go, the next upload goes through.
    assert put(api_client, user, fx.jpeg()).status_code == 200


@pytest.mark.django_db(transaction=True)
def test_two_uploads_at_once_are_decoded_one_after_the_other(api_client, monkeypatch):
    real = avatars.process_photo
    active, peak, lock = [0], [0], threading.Lock()

    def measured(data):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        try:
            time.sleep(0.3)
            return real(data)
        finally:
            with lock:
                active[0] -= 1

    monkeypatch.setattr(avatars, "process_photo", measured)
    users = [verified(), verified(), verified()]

    def upload_for(user):
        return lambda: put(api_client.__class__(), user, fx.jpeg(colour=(user.pk.int % 200, 5, 5)))

    results = run_together(*(upload_for(user) for user in users))

    assert [r.status_code for r in results] == [200, 200, 200]
    assert peak[0] == 1
    assert Avatar.objects.count() == 3


@pytest.mark.django_db(transaction=True)
def test_the_gate_is_released_when_a_decode_fails(api_client):
    user = verified()
    assert put(api_client, user, fx.SVG).status_code == 400
    # If the failed attempt had kept the gate, this would wait for lock_timeout and answer 503.
    started = time.monotonic()
    assert put(api_client, user, fx.jpeg()).status_code == 200
    assert time.monotonic() - started < 5


@pytest.mark.django_db(transaction=True)
def test_an_upload_waits_for_the_accounts_row_lock_and_then_sees_a_block(api_client):
    """A moderator's Block holds the account row; the upload queues behind it, then re-checks."""
    user = verified()
    holding, release = threading.Event(), threading.Event()

    def moderator():
        from django.db import transaction

        with transaction.atomic():
            User.objects.select_for_update().get(pk=user.pk)
            User.objects.filter(pk=user.pk).update(avatar_uploads_blocked=True)
            holding.set()
            release.wait(timeout=20)
        connection.close()

    thread = threading.Thread(target=moderator)
    thread.start()
    assert holding.wait(timeout=10)
    results = []

    def upload():
        results.append(put(api_client.__class__(), user, fx.jpeg()))
        connection.close()

    uploader = threading.Thread(target=upload)
    uploader.start()
    time.sleep(0.5)  # the upload is now waiting for the row
    release.set()
    thread.join(timeout=20)
    uploader.join(timeout=20)

    assert results[0].status_code == 403 and code_of(results[0]) == "photo_uploads_blocked"
    assert not Avatar.objects.exists()


def test_the_timestamps_use_the_clock_it_is_given(monkeypatch):
    user = verified()
    moment = timezone.now().replace(microsecond=0)
    avatars.save_photo(user.pk, fx.jpeg(), now=moment)
    row = Avatar.objects.get(user=user)
    assert row.created_at == row.updated_at == moment
