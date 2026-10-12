"""Editing the platform settings in Django Admin (Part 10): who may, and what the log says."""

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.accounts.models import Role
from apps.accounts.tests.factories import UserFactory
from apps.core.models import PlatformSettings

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("role_groups")]

URL = "admin:core_platformsettings_change"


def form(**changes):
    row = PlatformSettings.objects.get(pk=1)
    data = {
        name: getattr(row, name)
        for name in (
            "report_threshold",
            "report_window_hours",
            "report_min_account_age_hours",
            "confidence_threshold",
            "fact_posts_per_day",
            "emergency_duration_hours",
            "emergency_posts_per_day",
            "emergency_min_account_age_days",
            "emergency_min_reputation",
            "emergency_report_threshold",
            "emergency_false_cooldown_days",
        )
    }
    return {**data, **changes}


def last_entry():
    return LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(PlatformSettings)
    ).latest("action_time")


def test_a_change_is_logged_with_the_old_and_new_values(client):
    senior = UserFactory(role=Role.SENIOR_MODERATOR)
    client.force_login(senior)
    row = PlatformSettings.objects.get(pk=1)
    old_report, old_confidence = row.report_threshold, row.confidence_threshold
    response = client.post(
        reverse(URL, args=[1]),
        form(report_threshold=old_report + 2, confidence_threshold=old_confidence - 5),
    )
    assert response.status_code == 302
    entry = last_entry()
    assert entry.get_change_message() == (
        f"Report threshold: {old_report} → {old_report + 2}; "
        f"Confidence threshold: {old_confidence} → {old_confidence - 5}."
    )
    assert (entry.user, entry.action_flag) == (senior, CHANGE)


def test_an_emergency_limit_is_logged_the_same_way(client):
    client.force_login(UserFactory(role=Role.SENIOR_MODERATOR))
    old = PlatformSettings.objects.get(pk=1).emergency_report_threshold
    client.post(reverse(URL, args=[1]), form(emergency_report_threshold=old + 1))
    assert last_entry().get_change_message() == (f"Emergency report threshold: {old} → {old + 1}.")


def test_a_save_that_changes_nothing_logs_no_values(client):
    client.force_login(UserFactory(role=Role.SENIOR_MODERATOR))
    client.post(reverse(URL, args=[1]), form())
    assert "→" not in last_entry().get_change_message()


def test_the_new_values_take_effect_at_once_through_the_cache(client):
    from apps.core.services import get_platform_settings

    client.force_login(UserFactory(role=Role.SENIOR_MODERATOR))
    old = get_platform_settings().report_threshold
    client.post(reverse(URL, args=[1]), form(report_threshold=old + 1))
    assert get_platform_settings().report_threshold == old + 1


def test_a_value_out_of_range_is_refused_and_logs_nothing(client):
    client.force_login(UserFactory(role=Role.SENIOR_MODERATOR))
    before = LogEntry.objects.count()
    response = client.post(reverse(URL, args=[1]), form(confidence_threshold=101))
    assert response.status_code == 200 and b"errorlist" in response.content
    assert LogEntry.objects.count() == before


def test_the_history_page_shows_the_values_to_a_senior(client):
    client.force_login(UserFactory(role=Role.SENIOR_MODERATOR))
    old = PlatformSettings.objects.get(pk=1).report_threshold
    client.post(reverse(URL, args=[1]), form(report_threshold=old + 3))
    page = client.get(reverse("admin:core_platformsettings_history", args=[1]))
    assert f"Report threshold: {old} → {old + 3}." in page.content.decode()
