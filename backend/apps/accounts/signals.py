"""Signal receivers (connected in AccountsConfig.ready)."""

from allauth.account.signals import email_confirmed
from allauth.socialaccount.signals import social_account_added
from django.dispatch import receiver

from apps.accounts.services import mark_email_verified, mark_email_verified_by_google


@receiver(email_confirmed)
def verify_user_email(sender, request, email_address, **kwargs):
    mark_email_verified(email_address)


@receiver(social_account_added)
def verify_email_linked_by_google(sender, request, sociallogin, **kwargs):
    """A Google sign-in that matched an existing account by email proves the inbox (allauth never
    sends `email_confirmed` for it). Only the email-authentication path sets the attribute."""
    email = getattr(sociallogin, "_did_authenticate_by_email", None)
    if email:
        mark_email_verified_by_google(sociallogin.user, email)
