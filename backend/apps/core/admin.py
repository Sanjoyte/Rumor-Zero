from django.contrib import admin
from django.utils.text import capfirst

from apps.core.admin_mixins import HistoryNeedsLog
from apps.core.models import PlatformSettings

# The header (templates/admin/base_site.html) shows the logo and this name; the browser tab says it
# too, and so does the login page.
admin.site.site_header = "Rumor Zero moderation"
admin.site.site_title = "Rumor Zero moderation"
admin.site.index_title = "Moderation"


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(HistoryNeedsLog, admin.ModelAdmin):
    """The thresholds (ARCHITECTURE §2, §3). **Senior moderators edit them** (they hold
    `core.change_platformsettings`, the six emergency limits included); a moderator holds
    `view_platformsettings` and gets the page read-only. Every change is logged with its old and
    new values, so the History page and the admin log show who moved a threshold and from what."""

    readonly_fields = ("updated_by", "updated_at")

    def has_add_permission(self, request):
        # One row only (id=1): it is made by the seeding migration, this is for a wiped table.
        return super().has_add_permission(request) and not PlatformSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def construct_change_message(self, request, form, formsets, add=False):
        """ "Report threshold: 5 → 3; Confidence threshold: 85 → 90." Django's own message only
        names the fields."""
        changed = getattr(form, "changed_data", [])
        if add or not changed or not hasattr(form, "initial"):
            return super().construct_change_message(request, form, formsets, add)
        parts = []
        for name in changed:
            label = capfirst(str(form.fields[name].label or name).replace("_", " "))
            parts.append(f"{label}: {form.initial.get(name)} → {form.cleaned_data[name]}")
        return "; ".join(parts) + "."
