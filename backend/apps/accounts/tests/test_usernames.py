"""Usernames for new Google accounts: from the first name, never from the email."""

import random
import re

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.accounts.usernames import generate_username, slugify_name
from apps.accounts.validators import RESERVED_USERNAMES, USERNAME_PATTERN

pytestmark = pytest.mark.django_db

NOTHING_TAKEN = {"is_taken": lambda username: False}


def seeded():
    return random.Random(1234)


@pytest.mark.parametrize(
    ("given_name", "expected"),
    [
        ("Ada", "ada"),
        ("José", "jose"),
        ("Mary-Jane", "mary_jane"),
        ("  Anne  Marie  ", "anne_marie"),
        ("O'Brien", "o_brien"),
        ("Ｏｌｉｖｉａ", "olivia"),
        ("李", ""),
        ("সঞ্জয়", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_the_name_is_reduced_to_a_slug(given_name, expected):
    assert slugify_name(given_name) == expected


def test_the_slug_is_cut_before_trailing_underscores_are_stripped():
    # 19 letters, then "-" (becomes "_") at position 20 of the slug: cutting first leaves no "_".
    assert slugify_name("a" * 19 + "-bcd") == "a" * 19


def test_a_free_name_is_used_as_it_is():
    assert generate_username("Ada", **NOTHING_TAKEN) == "ada"


def test_a_taken_name_gets_four_random_digits():
    UserFactory(username="ada")
    result = generate_username("Ada", rng=seeded())
    assert re.fullmatch(r"ada_\d{4}", result)


def test_a_taken_suffix_is_skipped():
    rng = seeded()
    first = f"ada_{random.Random(1234).randrange(10000):04d}"
    UserFactory(username="ada")
    UserFactory(username=first)
    result = generate_username("Ada", rng=rng)
    assert re.fullmatch(r"ada_\d{4}", result)
    assert result != first


def test_a_short_name_always_gets_a_suffix():
    result = generate_username("Al", **NOTHING_TAKEN, rng=seeded())
    assert re.fullmatch(r"al_\d{4}", result)


def test_a_long_name_is_cut_to_twenty_characters():
    assert generate_username("Bartholomew" * 4, **NOTHING_TAKEN) == "bartholomewbartholom"


@pytest.mark.parametrize("given_name", ["Admin", "moderator", "Rumor Zero", "ROOT"])
def test_a_reserved_name_falls_back_to_member(given_name):
    result = generate_username(given_name, **NOTHING_TAKEN, rng=seeded())
    assert re.fullmatch(r"member_[a-z0-9]{6}", result)


@pytest.mark.parametrize("given_name", ["李", "", None, "!!!"])
def test_a_name_with_no_latin_letters_falls_back_to_member(given_name):
    result = generate_username(given_name, **NOTHING_TAKEN, rng=seeded())
    assert re.fullmatch(r"member_[a-z0-9]{6}", result)


def test_the_fallback_is_random_without_a_seed():
    names = {generate_username("", **NOTHING_TAKEN) for _ in range(5)}
    assert len(names) > 1


def test_every_candidate_taken_ends_in_a_uuid_fallback():
    result = generate_username("Ada", is_taken=lambda username: True, rng=seeded())
    assert re.fullmatch(r"member_[0-9a-f]{12}", result)


def test_a_seeded_rng_is_deterministic():
    kwargs = {"is_taken": lambda username: username == "ada"}
    assert generate_username("Ada", rng=seeded(), **kwargs) == generate_username(
        "Ada", rng=seeded(), **kwargs
    )


@pytest.mark.parametrize(
    "given_name",
    ["Ada", "José", "Mary-Jane", "Admin", "Al", "李", "", None, "x" * 80, "A.B.C", "__"],
)
def test_every_result_is_a_valid_unreserved_username(given_name):
    for _ in range(20):
        result = generate_username(given_name, **NOTHING_TAKEN)
        assert re.fullmatch(USERNAME_PATTERN, result)
        assert result not in RESERVED_USERNAMES
