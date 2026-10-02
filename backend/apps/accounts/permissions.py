"""API permissions (ARCHITECTURE §7)."""

from rest_framework.permissions import BasePermission


class IsEmailVerified(BasePermission):
    """Unverified accounts are read-only: 403 `email_unverified` on the views that use this.

    An anonymous request fails too, and DRF answers it with 401 (an authenticator is configured).
    """

    code = "email_unverified"
    message = "Verify your email address first. Check your inbox for the link."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_email_verified)
