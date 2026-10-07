"""The branded emails: wording, sender, links, logo and the Brevo setup (ARCHITECTURE §7, §14).

Every email goes through the real flows (sign-up, resend, reset request), so the context is what
production sends.
"""

import json
import re
from email.utils import parseaddr

import pytest
from allauth.account.adapter import get_adapter
from anymail.backends.brevo import EmailBackend as BrevoBackend
from django.core import mail

from apps.accounts.tests.conftest import (
    PASSWORD_REQUEST_URL,
    RESEND_URL,
    access_token_for,
    post_json,
    signup,
)
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

ORIGIN = "http://localhost:3000"
LOGO_URL = f"{ORIGIN}/brand/email-logo.png"
KINDS = ["signup", "verify", "reset"]
SUBJECTS = {
    "signup": "[Rumor Zero] Welcome to Rumor Zero: verify your email",
    "verify": "[Rumor Zero] Verify your email",
    "reset": "[Rumor Zero] Reset your password",
}


@pytest.fixture
def emails(site_client, api_client, turnstile):
    """One of each email, sent through the real endpoints, in the order of KINDS."""
    assert signup(site_client).status_code == 200
    other = UserFactory()
    headers = {"HTTP_AUTHORIZATION": f"Bearer {access_token_for(other)}"}
    assert api_client.post(RESEND_URL, **headers).status_code == 204
    exists = UserFactory(email="exists@example.test")
    assert post_json(site_client, PASSWORD_REQUEST_URL, {"email": exists.email}).status_code == 200
    assert len(mail.outbox) == 3
    return dict(zip(KINDS, mail.outbox, strict=True))


@pytest.fixture(params=KINDS)
def kind(request):
    return request.param


@pytest.fixture
def message(emails, kind):
    return emails[kind]


def html_of(message):
    assert len(message.alternatives) == 1
    content, mimetype = message.alternatives[0]
    assert mimetype == "text/html"
    return content


def test_subject_and_sender(message, kind, settings):
    assert message.subject == SUBJECTS[kind]
    assert message.from_email == settings.DEFAULT_FROM_EMAIL


def test_every_email_has_a_text_part_and_an_html_alternative(message):
    assert message.body.strip()
    html = html_of(message)
    assert html.startswith("<!DOCTYPE html>")
    assert 'lang="en"' in html
    assert "xmlns" not in html  # an XHTML namespace URL would be a link to someone else's host


def test_every_link_points_at_the_frontend(message):
    html = html_of(message)
    urls = re.findall(r"https?://[^\s\"'<>)]+", message.body + html)
    assert urls
    assert all(url.startswith(ORIGIN + "/") for url in urls), urls
    attributes = re.findall(r'(?:href|src)="([^"]*)"', html)
    assert attributes
    assert all(value.startswith(ORIGIN + "/") for value in attributes), attributes


def test_no_backend_host_or_stock_allauth_wording(message):
    html = html_of(message)
    for text in (message.body, html):
        assert "testserver" not in text
        assert "localhost:8000" not in text
        assert "Hello from" not in text
        assert "Thank you for using" not in text
        assert "example.com" not in text


def test_the_logo_is_in_the_html_only(message):
    html = html_of(message)
    images = re.findall(r"<img\b[^>]*>", html)
    assert len(images) == 1
    image = images[0]
    assert f'src="{LOGO_URL}"' in image
    assert 'alt="Rumor Zero"' in image
    assert 'width="160"' in image
    assert "#283044" in html  # the plate colour (Stitch inverse-surface) behind the logo
    assert "<img" not in message.body
    assert "email-logo" not in message.body


def test_the_text_part_is_plain_text(message):
    assert "<" not in message.body
    assert "&amp;" not in message.body
    assert "{{" not in message.body and "{%" not in message.body


def test_no_line_is_long_enough_to_force_quoted_printable(message):
    for part in (message.body, html_of(message)):
        assert max(len(line) for line in part.splitlines()) < 998
    assert b"quoted-printable" not in message.message().as_bytes().lower()


def test_the_button_uses_the_secondary_token(message):
    html = html_of(message)
    assert "#006398" in html  # Stitch `secondary`, copied because email clients can't read CSS vars
    assert html.count("<a ") == 2  # the button and the paste-this-link fallback


def test_the_wording(emails):
    verify, signup_mail, reset = emails["verify"], emails["signup"], emails["reset"]
    assert "Welcome to Rumor Zero" in signup_mail.body
    assert "Welcome" not in verify.body
    for mail_ in (signup_mail, verify):
        assert "24 hours" in mail_.body
        assert "/verify-email/" in mail_.body
    assert "24 hours" in reset.body
    assert "ignore this email" in reset.body
    assert "/reset-password/" in reset.body
    assert "/verify-email/" not in reset.body


def test_the_signup_variants_use_the_welcome_templates(emails):
    assert "Welcome to Rumor Zero" in html_of(emails["signup"])
    assert "Welcome" not in html_of(emails["verify"])


def test_an_allauth_email_without_a_template_of_ours_renders_without_the_backend_host():
    user = UserFactory()
    rendered = get_adapter().render_mail(
        "account/email/password_changed", user.email, {"user": user}
    )
    assert "Your password has been changed." in rendered.body
    assert "Hello from" not in rendered.body
    assert "testserver" not in rendered.body
    assert not getattr(rendered, "alternatives", [])


# ---------- the Brevo configuration, without the network ----------


def brevo_payload(message):
    """What anymail's Brevo backend would POST for `message` (no request is made)."""
    backend = BrevoBackend(api_key="xkeysib-test-only")
    payload = backend.build_message_payload(message, backend.send_defaults)
    assert payload.get_api_endpoint() == "smtp/email"
    assert payload.headers["api-key"] == "xkeysib-test-only"
    return json.loads(payload.serialize_data())


def test_brevo_gets_the_sender_subject_text_and_html(message, kind, settings):
    name, address = parseaddr(settings.DEFAULT_FROM_EMAIL)
    data = brevo_payload(message)
    assert data["sender"] == {"email": address, "name": name}
    assert data["to"] == [{"email": message.to[0]}]
    assert data["subject"] == SUBJECTS[kind]
    assert data["textContent"] == message.body
    assert data["htmlContent"] == html_of(message)


def test_the_brevo_backend_is_what_production_selects(tmp_path):
    from rumor_zero.env_helpers import email_config

    backend, _, anymail = email_config(
        "brevo", base_dir=tmp_path, brevo_api_key="xkeysib-test-only"
    )
    assert backend == "anymail.backends.brevo.EmailBackend"
    assert anymail == {"BREVO_API_KEY": "xkeysib-test-only"}


def test_the_emails_go_through_anymails_test_backend(site_client, api_client, turnstile, settings):
    settings.EMAIL_BACKEND = "anymail.backends.test.EmailBackend"
    settings.ANYMAIL = {}
    assert signup(site_client).status_code == 200
    exists = UserFactory(email="exists@example.test")
    assert post_json(site_client, PASSWORD_REQUEST_URL, {"email": exists.email}).status_code == 200

    assert len(mail.outbox) == 2
    for sent, kind in zip(mail.outbox, ("signup", "reset"), strict=True):
        params = sent.anymail_test_params
        assert params["subject"] == SUBJECTS[kind]
        assert params["text_body"] == sent.body
        assert params["html_body"].startswith("<!DOCTYPE html>")
        assert params["from"].addr_spec == parseaddr(settings.DEFAULT_FROM_EMAIL)[1]
        assert [to.addr_spec for to in params["to"]] == sent.to
        assert sent.anymail_status.status == {"sent"}
