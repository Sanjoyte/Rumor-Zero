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


class PhotoUploadsAllowed(BasePermission):
    """403 `photo_uploads_blocked` while a moderator has turned off photo uploads for the account
    (Part 14B). Like every permission it runs before the throttle, so a refusal never counts
    against `avatar_upload`."""

    code = "photo_uploads_blocked"
    message = "A moderator turned off photo uploads for your account."

    def has_permission(self, request, view):
        user = request.user
        return not (user and user.is_authenticated and user.avatar_uploads_blocked)
