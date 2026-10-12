"""The admin header shows the logo and "Rumor Zero moderation" (ARCHITECTURE §8, §14)."""

import pytest
from django.contrib import admin
from django.contrib.staticfiles import finders
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

LOGO = "core/brand/logo-admin.png"


def test_the_site_names_are_set():
    assert admin.site.site_header == "Rumor Zero moderation"
    assert admin.site.site_title == "Rumor Zero moderation"
    assert admin.site.index_title == "Moderation"


def test_the_logo_file_exists_where_the_header_points():
    assert finders.find(LOGO) is not None


def test_the_login_page_has_the_logo_and_the_name(client):
    page = client.get(reverse("admin:login"))
    body = page.content.decode()
    assert page.status_code == 200
    assert LOGO in body and 'alt=""' in body
    assert "Rumor Zero moderation" in body
    assert "Django administration" not in body


def test_the_index_page_has_the_logo_and_the_name(client):
    client.force_login(UserFactory(is_superuser=True))
    body = client.get(reverse("admin:index")).content.decode()
    assert LOGO in body and 'alt=""' in body and 'height="32"' in body
    assert "Rumor Zero moderation" in body
    assert "<title>Moderation | Rumor Zero moderation</title>" in body


def test_the_logo_is_decorative_because_the_name_sits_beside_it(client):
    body = client.get(reverse("admin:login")).content.decode()
    image = body[body.index("<img src=") :]
    assert image.split(">")[0].count("alt=") == 1 and 'alt=""' in image.split(">")[0]
