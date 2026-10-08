"""Account services: email verification state and the resend flow (ARCHITECTURE §7)."""

from allauth.account.internal.flows.email_verification import send_verification_email_for_user
from allauth.account.models import EmailAddress
from allauth.core import ratelimit

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


def mark_email_verified_by_google(user, email):
    """Mark `email` verified for `user`, who just linked a Google account that proved it.

    Runs inside allauth's `connect()`, after `wipe_password`: an address that was unverified has
    already cost its password. Creates the `EmailAddress` row when the user has none (accounts made
    by `create_user` or in the admin have none).
    """
    email = email.strip().lower()
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
