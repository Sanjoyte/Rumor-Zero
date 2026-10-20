"""Signal receivers (connected in AccountsConfig.ready)."""

from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed
from allauth.socialaccount.signals import social_account_added
from django.db import transaction
from django.dispatch import receiver

from apps.accounts.services import (
    mark_email_verified,
    mark_email_verified_by_google,
    send_google_connected_email,
)


@receiver(email_confirmed)
def verify_user_email(sender, request, email_address, **kwargs):
    mark_email_verified(email_address)


@receiver(social_account_added)
def verify_email_linked_by_google(sender, request, sociallogin, **kwargs):
    """A Google sign-in that matched an existing account by email proves the inbox (allauth never
    sends `email_confirmed` for it). Only the email-authentication path sets the attribute."""
    email = getattr(sociallogin, "_did_authenticate_by_email", None)
    if email:
        user = sociallogin.user
        was_verified = EmailAddress.objects.filter(
            user_id=user.pk, email__iexact=email, verified=True
        ).exists()
        mark_email_verified_by_google(user, email)
        # Part 14: the account's owner hears that Google now opens it. A Google *sign-up* never
        # gets here (it fires `user_signed_up`), and nor does a returning Google sign-in. An
        # address that was not verified had cost the account its password (`wipe_password`, which
        # ran before this signal).
        removed = not was_verified and not user.has_usable_password()
        transaction.on_commit(
            lambda: send_google_connected_email(request, user, password_removed=removed)
        )
