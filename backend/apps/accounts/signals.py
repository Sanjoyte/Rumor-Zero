"""Signal receivers (connected in AccountsConfig.ready)."""

from allauth.account.signals import email_confirmed
from django.dispatch import receiver

from apps.accounts.services import mark_email_verified


@receiver(email_confirmed)
def verify_user_email(sender, request, email_address, **kwargs):
    mark_email_verified(email_address)
