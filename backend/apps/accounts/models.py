import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import Group, PermissionsMixin
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from apps.accounts.validators import (
    USERNAME_PATTERN,
    normalize_email,
    normalize_username,
    validate_username,
)


class Role(models.TextChoices):
    USER = "user", "User"
    MODERATOR = "moderator", "Moderator"
    SENIOR_MODERATOR = "senior_moderator", "Senior moderator"


MODERATORS_GROUP = "Moderators"
SENIORS_GROUP = "Senior moderators"
# Cumulative: a senior moderator is also a moderator. Part 10 gives the senior group only the
# extra permissions.
ROLE_GROUPS = {
    Role.USER: (),
    Role.MODERATOR: (MODERATORS_GROUP,),
    Role.SENIOR_MODERATOR: (MODERATORS_GROUP, SENIORS_GROUP),
}
MANAGED_GROUP_NAMES = (MODERATORS_GROUP, SENIORS_GROUP)
# Written only by `apps/reputation/services.py` (and `recompute_reputation`), never by a save.
REPUTATION_FIELDS = frozenset({"reputation_score", "reputation_sample"})
# What a full `User.save()` leaves alone: the score (Part 11B) and the emergency block, which only
# `apps/moderation/services.py` writes, with `.update()` (Part 11C).
SERVICE_OWNED_FIELDS = REPUTATION_FIELDS | {"emergency_blocked_until"}


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        if not username:
            raise ValueError("A username is required.")
        user = self.model(
            email=normalize_email(email), username=normalize_username(username), **extra_fields
        )
        # password=None makes the password unusable (Google-only accounts), never NULL.
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        from allauth.account.models import EmailAddress

        # role stays "user": the superuser keeps admin access through is_superuser.
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        # Created from your own PC, so the address counts as verified (user decision 2026-10-01).
        extra_fields.setdefault("is_email_verified", True)
        user = self.create_user(email, username, password, **extra_fields)
        EmailAddress.objects.create(
            user=user, email=user.email, verified=user.is_email_verified, primary=True
        )
        return user

    def get_by_natural_key(self, email):
        return self.get(**{self.model.USERNAME_FIELD: normalize_email(email)})


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=30, unique=True, validators=[validate_username])
    email = models.EmailField(max_length=254, unique=True)
    display_name = models.CharField(max_length=50, blank=True)
    bio = models.CharField(max_length=280, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    is_email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    # null = no profile photo (initials); set by the avatar service in Part 14B.
    avatar_version = models.CharField(max_length=16, null=True, blank=True)  # noqa: DJ001
    avatar_uploads_blocked = models.BooleanField(default=False)
    # Written only by apps/reputation/services.py (Part 11B).
    reputation_score = models.SmallIntegerField(
        default=50, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    reputation_sample = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    # Written only by apps/moderation/services.py (Part 11C): the end of the latest block still
    # standing (`rules.standing_block_end` of the account's block rows).
    emergency_blocked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=Role.values), name="accounts_user_role_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(reputation_score__gte=0, reputation_score__lte=100),
                name="accounts_user_reputation_score_range",
            ),
            models.CheckConstraint(
                condition=models.Q(reputation_sample__gte=0),
                name="accounts_user_reputation_sample_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(username__regex=USERNAME_PATTERN),
                name="accounts_user_username_format",
            ),
            models.CheckConstraint(
                condition=models.Q(email=Lower("email")), name="accounts_user_email_lowercase"
            ),
        ]

    def __str__(self):
        return self.username

    @classmethod
    def from_db(cls, db, field_names, values):
        user = super().from_db(db, field_names, values)
        # Remember the loaded role (deferred fields stay untouched) to sync groups only on change.
        user._loaded_role = user.__dict__.get("role")
        return user

    def clean(self):
        super().clean()
        self.email = normalize_email(self.email)
        self.username = normalize_username(self.username)

    def save(self, *args, **kwargs):
        self.email = normalize_email(self.email)
        self.username = normalize_username(self.username)
        self.is_staff = self.is_superuser or self.role != Role.USER

        update_fields = kwargs.get("update_fields")
        touches_access = update_fields is None or bool(
            {"role", "is_superuser"} & set(update_fields)
        )
        if update_fields is not None and touches_access:
            kwargs["update_fields"] = {*update_fields, "is_staff"}
        sync_groups = touches_access and (
            self._state.adding or getattr(self, "_loaded_role", None) != self.role
        )
        if update_fields is None and not self._state.adding and not kwargs.get("force_insert"):
            # A full save of a loaded account (allauth's `set_password`, the admin form) would
            # write back the score it read earlier in the request, undoing a ledger write that
            # committed meanwhile (Part 11B), and likewise an emergency block (Part 11C). It
            # writes every other loaded field instead.
            deferred = self.get_deferred_fields()
            kwargs["update_fields"] = [
                field.attname
                for field in self._meta.concrete_fields
                if not field.primary_key
                and field.attname not in deferred
                and field.attname not in SERVICE_OWNED_FIELDS
            ]

        super().save(*args, **kwargs)

        if sync_groups:
            self._sync_groups()
        if touches_access:
            self._loaded_role = self.role

    def _sync_groups(self):
        """Make the role groups match the role. Other groups are left alone."""
        wanted = [Group.objects.get_or_create(name=name)[0] for name in ROLE_GROUPS[self.role]]
        stale = self.groups.filter(name__in=MANAGED_GROUP_NAMES).exclude(
            pk__in=[group.pk for group in wanted]
        )
        self.groups.remove(*stale)
        self.groups.add(*wanted)
