"""Startup: allauth's deferred token libraries are loaded before the first request."""

import json

from apps.accounts.apps import TOKEN_LIBRARIES
from apps.core.tests.test_settings import production_env, run_python

PROBE = """
import json, sys
import django
django.setup()
from apps.accounts.apps import TOKEN_LIBRARIES
print(json.dumps({name: name in sys.modules for name in TOKEN_LIBRARIES}))
"""


def test_the_token_libraries_are_loaded_by_django_setup_not_on_the_first_sign_in():
    """A fresh interpreter, so nothing else has imported them. Without this, two simultaneous
    first sign-ins on a cold server can race inside the import and answer 500."""
    env = production_env()
    env["DJANGO_SETTINGS_MODULE"] = "rumor_zero.settings"
    result = run_python(["-c", PROBE], env)
    assert result.returncode == 0, result.stderr
    loaded = json.loads(result.stdout.strip().splitlines()[-1])
    assert loaded == dict.fromkeys(TOKEN_LIBRARIES, True)
