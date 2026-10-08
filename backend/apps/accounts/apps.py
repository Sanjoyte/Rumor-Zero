import importlib

from django.apps import AppConfig

# allauth defers `jwt` and `cryptography` until the first token it makes
# (allauth/core/internal/deferred.py). Two sign-ins arriving together at a cold server then import
# them from two threads at once, and one sees a half-built package: "cannot access submodule
# 'ciphers' of module 'cryptography.hazmat.primitives' (most likely due to a circular import)",
# a 500 on sign-up (and on "Continue with Google"). Importing what the token code touches at
# startup closes that window.
TOKEN_LIBRARIES = (
    "jwt",
    "jwt.algorithms",
    "jwt.exceptions",
    "cryptography.hazmat.primitives.ciphers",
    "cryptography.hazmat.primitives.ciphers.algorithms",
    "cryptography.hazmat.primitives.ciphers.modes",
    # Google's certificates (allauth/socialaccount/internal/jwtkit.py), loaded on the first sign-in.
    "cryptography.x509",
    "cryptography.hazmat.backends",
)


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        from apps.accounts import signals  # noqa: F401  (connects the receivers)

        for module in TOKEN_LIBRARIES:
            importlib.import_module(module)
