"""Django Admin for reports: a read-only list (Part 8). Moderators get permissions in Part 10."""

import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.accounts.tests.factories import UserFactory
from apps.reports.models import Report, ReportReason
from apps.reports.tests.factories import ReportFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def superuser(client):
    user = User.objects.create_superuser(
        email="root@example.test", username="root_user", password="S3cure-pass-phrase!"
    )
    client.force_login(user)
    return user


def test_reports_are_registered_in_the_admin():
    assert Report in admin.site._registry


def test_the_changelist_renders_filters_searches_and_never_prints_the_details(client, superuser):
    ReportFactory(
        reporter__username="needle_reporter",
        reason=ReportReason.OTHER,
        details="a private accusation",
        post__content="the reported post",
    )
    ReportFactory(reporter__username="other_reporter", dismissed=True)
    url = reverse("admin:reports_report_changelist")
    page = client.get(url, {"q": "needle_reporter"})
    assert page.status_code == 200
    assert b"needle_reporter" in page.content and b"other_reporter" not in page.content
    assert b"a private accusation" not in page.content  # the list never shows the text
    for query in (
        {"status": "dismissed"},
        {"reason": "other"},
        {"counts_toward_threshold__exact": "1"},
    ):
        assert client.get(url, query).status_code == 200


def test_one_report_page_shows_the_details_to_those_allowed_to_view_it(client, superuser):
    report = ReportFactory(reason=ReportReason.OTHER, details="a private accusation")
    page = client.get(reverse("admin:reports_report_change", args=[report.pk]))
    assert page.status_code == 200
    assert b"a private accusation" in page.content


def test_it_is_read_only(client, superuser):
    report = ReportFactory()
    assert client.get(reverse("admin:reports_report_add")).status_code == 403
    assert client.post(reverse("admin:reports_report_change", args=[report.pk])).status_code == 403
    assert client.post(reverse("admin:reports_report_delete", args=[report.pk])).status_code == 403
    assert Report.objects.filter(pk=report.pk).exists()


def test_a_moderator_without_the_permission_cannot_open_it_yet(client):
    moderator = UserFactory(role=Role.MODERATOR)  # no model permissions until Part 10
    client.force_login(moderator)
    assert client.get(reverse("admin:reports_report_changelist")).status_code == 403


def test_a_moderator_granted_view_permission_can_read_but_not_change(client):
    moderator = UserFactory(role=Role.MODERATOR)
    moderator.user_permissions.set(Permission.objects.filter(codename="view_report"))
    client.force_login(moderator)
    report = ReportFactory()
    assert client.get(reverse("admin:reports_report_changelist")).status_code == 200
    assert client.get(reverse("admin:reports_report_add")).status_code == 403
    assert client.post(reverse("admin:reports_report_delete", args=[report.pk])).status_code == 403
