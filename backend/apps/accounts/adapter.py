"""allauth account adapter (ARCHITECTURE §7)."""

import logging
from smtplib import SMTPException

from allauth.account.adapter import DefaultAccountAdapter
from anymail.exceptions import AnymailError
from django.conf import settings

from apps.accounts.validators import normalize_username

logger = logging.getLogger(__name__)


class AccountAdapter(DefaultAccountAdapter):
    def clean_username(self, username, shallow=False):
        # allauth's uniqueness check only lowercases, so fold NFKC first ("Ａｄａ" is "ada").
        return super().clean_username(normalize_username(username), shallow=shallow)

    def login(self, request, user):
        super().login(request, user)
        # The token session lives as long as a refresh token, and each refresh saves it again, so
        # the lifetime slides. Admin sessions keep SESSION_COOKIE_AGE.
        request.session.set_expiry(settings.REFRESH_TOKEN_SECONDS)

    def add_message(
        self,
        request,
        level,
        message_template=None,
        message_context=None,
        extra_tags="",
        message=None,
    ):
        # Headless-only: nothing renders Django messages, and storing one would set a `messages`
        # cookie on the frontend origin (allauth skips this only for headless-marked requests).
        return None

    def send_mail(self, template_prefix, email, context):
        # The templates link to the frontend and show the logo from it; the context allauth passes
        # has the (backend) request's host, which is never wanted in an email.
        context = {
            **context,
            "frontend_origin": settings.FRONTEND_ORIGIN,
            "email_logo_url": f"{settings.FRONTEND_ORIGIN}/brand/email-logo.png",
        }
        # A failed send must not turn a saved sign-up into a 500. Exception messages can contain
        # addresses or provider details, so only the class name is logged.
        try:
            super().send_mail(template_prefix, email, context)
        except (AnymailError, OSError, SMTPException) as exc:
            logger.error(
                "Could not send the %s email (%s)",
                template_prefix.rsplit("/", 1)[-1],
                type(exc).__name__,
            )
