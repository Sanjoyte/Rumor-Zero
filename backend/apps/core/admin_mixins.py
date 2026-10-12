"""Small pieces shared by several admins."""

from django.core.exceptions import PermissionDenied


class HistoryNeedsLog:
    """A object's History page lists Django's admin log entries for it, and Django lets anyone
    who may *view* the object open it. The log is seniors-only (decision 2026-10-11), so the page
    needs `admin.view_logentry` too. Put this first in the admin's bases. The History link is
    hidden from those who can't open it by `templates/admin/change_form_object_tools.html`."""

    def history_view(self, request, object_id, extra_context=None):
        if not request.user.has_perm("admin.view_logentry"):
            raise PermissionDenied
        return super().history_view(request, object_id, extra_context)
