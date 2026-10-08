"""allauth account and social-account adapters (ARCHITECTURE §7)."""

import logging
from smtplib import SMTPException

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from anymail.exceptions import AnymailError
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.accounts.usernames import generate_username
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


# What Google's ID token claims that we keep. Its name, picture and locale are not stored.
KEPT_GOOGLE_CLAIMS = ("sub", "email", "email_verified", "hd")
# Google is authoritative for an address only when it hosts it: Gmail, or a Workspace domain (the
# token then has `hd`). Any other address was verified when the Google account was created, and
# may have changed hands since (Google's ID-token guide).
AUTHORITATIVE_EMAIL_SUFFIX = "@gmail.com"


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Google sign-in rules (ARCHITECTURE §7). A sign-up must never pend: a pending social
    sign-up needs `X-Session-Token`, which AuthApiMiddleware strips."""

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        extra_data = sociallogin.account.extra_data or {}
        # Not a model field: kept for save_user, then dropped with the in-memory login.
        given_name = data.get("first_name") or extra_data.get("given_name") or ""
        sociallogin.rz_given_name = str(given_name)
        sociallogin.account.extra_data = {
            claim: extra_data[claim] for claim in KEPT_GOOGLE_CLAIMS if claim in extra_data
        }
        return user

    def pre_social_login(self, request, sociallogin):
        """Runs after allauth's lookup and before any link, password wipe or save.

        An error here is a 400 with its code and no `param`; no session or cookie is left behind.
        """
        if not any(address.verified for address in sociallogin.email_addresses):
            raise ValidationError(
                "Your Google account's email address isn't verified.",
                code="google_email_unverified",
            )
        if sociallogin.is_existing and not sociallogin.user.is_active:
            # allauth would link (and maybe wipe the password) before perform_login refuses.
            raise ValidationError("This account can't sign in.", code="account_inactive")
        matched_email = getattr(sociallogin, "_did_authenticate_by_email", None)
        if not matched_email:
            return  # a new user, or a returning Google link (uid): nothing to protect
        if sociallogin.user.is_staff:
            raise ValidationError(
                "Staff accounts log in with their password.", code="staff_password_login"
            )
        extra_data = sociallogin.account.extra_data or {}
        authoritative = matched_email.lower().endswith(AUTHORITATIVE_EMAIL_SUFFIX) or bool(
            extra_data.get("hd")
        )
        if not authoritative:
            raise ValidationError(
                "An account with this email already exists. Log in with your password.",
                code="google_link_requires_password",
            )

    def save_user(self, request, sociallogin, form=None):
        # New users only. The username comes from the first name, never from the email address
        # (it is public); Google's address is verified, so the account is too. display_name stays
        # blank: nothing from the Google profile becomes public until the user chooses it.
        user = sociallogin.user
        user.username = generate_username(getattr(sociallogin, "rz_given_name", ""))
        user.is_email_verified = True
        return super().save_user(request, sociallogin, form)
