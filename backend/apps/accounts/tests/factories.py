import factory

from apps.accounts.models import User

DEFAULT_PASSWORD = "correct-horse-battery-staple"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n:05d}")
    email = factory.LazyAttribute(lambda user: f"{user.username}@example.test")
    password = DEFAULT_PASSWORD

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Go through the manager so the password is hashed and the email normalised.
        return model_class.objects.create_user(*args, **kwargs)
