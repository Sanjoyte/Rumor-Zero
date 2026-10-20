"""Account services: email verification state and the resend flow, and the account settings
(profile, password) of Part 14 (ARCHITECTURE §7)."""

from allauth.account.adapter import get_adapter
from allauth.account.internal.flows.email_verification import send_verification_email_for_user
from allauth.account.models import EmailAddress
from allauth.core import ratelimit
from allauth.core.context import request_context
from django.conf import settings
from django.contrib.auth import HASH_SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.db import IntegrityError, transaction

from apps.accounts.models import User

# resend_verification_email() outcomes
SENT = "sent"
ALREADY_VERIFIED = "already_verified"
THROTTLED = "throttled"

DAILY_ACTION = "confirm_email_daily"


def mark_email_verified(email_address):
    """Set `users.is_email_verified` after allauth verified `email_address`.

    Only the address that is the user's current email counts. Returns the rows changed (0 or 1).
    """
    return User.objects.filter(pk=email_address.user_id, email__iexact=email_address.email).update(
        is_email_verified=True
    )


def _verify_address(user, email):
    """Make `email` a verified address of `user` and set `users.is_email_verified` when it is the
    account's own. Creates the `EmailAddress` row when the user has none (accounts made by
    `create_user` or in the admin have none). Returns the row."""
    address = EmailAddress.objects.filter(user_id=user.pk, email__iexact=email).first()
    if address is None:
        has_primary = EmailAddress.objects.filter(user_id=user.pk, primary=True).exists()
        address = EmailAddress.objects.create(
            user=user, email=email, verified=True, primary=not has_primary
        )
    elif not address.verified:
        address.verified = True
        address.save(update_fields=["verified"])
    if mark_email_verified(address):
        user.is_email_verified = True  # so a later full save in this request can't undo it
    return address


def mark_email_verified_by_google(user, email):
    """Mark `email` verified for `user`, who just linked a Google account that proved it.

    Runs inside allauth's `connect()`, after `wipe_password`: an address that was unverified has
    already cost its password.
    """
    return _verify_address(user, email.strip().lower())


def verify_email_by_staff(user):
    """A senior moderator marks `user`'s own address verified (Django Admin, Part 10; deferred from
    Part 2: for the person who can't get the email, or whose provider lost it). Returns True when
    something changed and False when the account already counts as verified. The caller logs it.
    """
    if user.is_email_verified:
        return False
    _verify_address(user, user.email)
    return True


def resend_verification_email(request, user):
    """Send the user a new verification link. `request` is Django's own request object.

    Returns SENT, ALREADY_VERIFIED or THROTTLED:
    - allauth's `confirm_email` rate (1 per 60 s per address) is the cooldown;
    - `confirm_email_daily` (10 per day per address) is a separate action, because allauth keeps
      one history per action and "per" type. The sign-up email doesn't count towards it.
    """
    if user.is_email_verified:
        return ALREADY_VERIFIED
    verified = EmailAddress.objects.filter(
        user_id=user.pk, email__iexact=user.email, verified=True
    ).exists()
    if verified:
        # The flag missed an earlier confirmation; a new link would be dead anyway.
        User.objects.filter(pk=user.pk).update(is_email_verified=True)
        user.is_email_verified = True
        return ALREADY_VERIFIED
    key = user.email.lower()
    if not ratelimit.consume(request, action=DAILY_ACTION, key=key, dry_run=True):
        return THROTTLED
    # Internal allauth API (MEMORY's re-check list). False means the 60 s cooldown said no.
    if not send_verification_email_for_user(request, user):
        return THROTTLED
    ratelimit.consume(request, action=DAILY_ACTION, key=key)
    return SENT


# ---------- Settings (Part 14) ----------

PROFILE_FIELDS = ("display_name", "username", "bio")


class UsernameTaken(Exception):
    """The username is another account's (or two renames raced for it and this one lost)."""


def update_profile(user, changes):
    """Save the `display_name`, `username` and `bio` in `changes` that differ from the account's.

    `changes` holds already-validated values. The save lists its fields, so it can never write
    `is_email_verified`, the role, or the score and emergency block that only their services own.
    Raises `UsernameTaken`. Returns the names of the fields that changed.
    """
    changed = [
        name for name in PROFILE_FIELDS if name in changes and changes[name] != getattr(user, name)
    ]
    if not changed:
        return []
    if "username" in changed and (
        User.objects.filter(username=changes["username"]).exclude(pk=user.pk).exists()
    ):
        raise UsernameTaken
    for name in changed:
        setattr(user, name, changes[name])
    try:
        # The savepoint keeps a lost race (the unique index) from poisoning an outer transaction.
        with transaction.atomic():
            user.save(update_fields=changed)
    except IntegrityError:
        raise UsernameTaken from None
    return changed


def change_password(request, user, new_password, *, session_key=None):
    """Set a new password and keep the device it was changed on signed in.

    A password change ends every other session at its next refresh, because the session's stored
    hash no longer matches the account's (`get_user` in allauth's token validation). This device's
    token session gets the new hash, under the lock on its `django_session` row that a refresh also
    takes (`tokens.py`), so a refresh running at the same moment can't write its older copy back.
    A session that is already gone is simply skipped: the password still changes. `request` is
    Django's own request object (allauth's mail needs it); the email goes out after the commit.
    """
    with transaction.atomic():
        has_session = (
            bool(session_key)
            and Session.objects.select_for_update().filter(session_key=session_key).exists()
        )
        user.set_password(new_password)
        user.save(update_fields=["password"])
        if has_session:
            store = SessionStore(session_key=session_key)
            store[HASH_SESSION_KEY] = user.get_session_auth_hash()
            store.save()
        transaction.on_commit(lambda: send_password_changed_email(request, user))


def _send(request, template_prefix, email, context):
    # The adapter adds the frontend origin and the logo and swallows a failed send. allauth reads
    # the request from its context variable, which is gone once the view has returned (a callback
    # run after the commit can be later than that), so it is set again here.
    with request_context(request):
        get_adapter(request).send_mail(template_prefix, email, context)


def send_password_changed_email(request, user):
    _send(
        request,
        "account/email/password_changed",
        user.email,
        {"user": user, "forgot_password_url": f"{settings.FRONTEND_ORIGIN}/forgot-password"},
    )


def send_google_connected_email(request, user, *, password_removed):
    """Tell the account that Continue with Google now opens it. `password_removed`: allauth wiped
    the password because the address had not been verified (the line then says so)."""
    _send(
        request,
        "account/email/google_connected",
        user.email,
        {
            "user": user,
            "password_removed": password_removed,
            "forgot_password_url": f"{settings.FRONTEND_ORIGIN}/forgot-password",
        },
    )
