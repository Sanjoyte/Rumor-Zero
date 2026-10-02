"""DRF authentication with allauth's JWT access tokens (ARCHITECTURE §7)."""

from allauth.headless.contrib.rest_framework.authentication import JWTTokenAuthentication
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from rest_framework.exceptions import AuthenticationFailed


class JWTAuthentication(JWTTokenAuthentication):
    """allauth's class returns a lazy user and skips the `is_active` check, so a deleted user's
    live token raised DoesNotExist (a 500). The user is loaded here instead (still one query):
    missing or inactive → 401."""

    def authenticate_credentials(self, key):
        user, payload = super().authenticate_credentials(key)
        try:
            active = user.is_active
        except (ObjectDoesNotExist, ValidationError, ValueError):
            raise AuthenticationFailed("Invalid token.") from None
        if not active:
            raise AuthenticationFailed("User inactive or deleted.")
        return user, payload
