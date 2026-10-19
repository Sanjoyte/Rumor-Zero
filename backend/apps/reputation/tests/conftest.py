import pytest

from apps.pipeline.tests.conftest import pipeline_cfg  # noqa: F401  (fixture)
from apps.posts.tests.conftest import auth_client, verified_user  # noqa: F401  (fixtures)


@pytest.fixture(autouse=True)
def _pinned_settings(pipeline_cfg):  # noqa: F811
    """Every test here starts from the same report and confidence settings (the seed comes from
    the developer's own `backend/.env`)."""
