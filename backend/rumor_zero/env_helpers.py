"""Small helpers for reading settings from the environment (django-environ)."""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured


def load_env_file(path):
    """Load a `.env` file if it exists. Variables already in the process env always win."""
    if Path(path).is_file():
        environ.Env.read_env(str(path), overwrite=False)


def require(env, name):
    """Return a non-empty variable, or fail naming the variable (never its value)."""
    value = env.str(name, default="")
    if not value.strip():
        raise ImproperlyConfigured(
            f"Set the {name} environment variable (see backend/.env.example)"
        )
    return value


def cache_config(redis_url):
    """Redis cache when a URL is set (protocol 2 for Upstash), else an in-process cache."""
    if redis_url:
        return {
            "default": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": redis_url,
                "OPTIONS": {
                    "protocol": 2,
                    "socket_connect_timeout": 5,
                    "socket_timeout": 5,
                },
            }
        }
    return {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
