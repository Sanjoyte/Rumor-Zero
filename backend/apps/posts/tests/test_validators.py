import json
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError

from apps.posts.validators import normalize_source, source_kind, validate_sources

VECTORS = json.loads((Path(__file__).parent / "source_vectors.json").read_text(encoding="ascii"))


def codes(exc_info):
    return [error.code for error in exc_info.value.error_list]


@pytest.mark.parametrize("case", VECTORS["accept"], ids=lambda case: repr(case["input"])[:60])
def test_accepted_sources_are_normalised(case):
    value = normalize_source(case["input"])
    assert value == case["value"]
    assert source_kind(value) == case["kind"]


@pytest.mark.parametrize("value", VECTORS["reject"], ids=lambda value: repr(value)[:60])
def test_rejected_sources(value):
    with pytest.raises(ValidationError):
        normalize_source(value)


@pytest.mark.parametrize("value", VECTORS["server_only_reject"])
def test_a_fake_punycode_label_is_refused_here(value):
    # The browser's URL parser accepts these; only the server checks the A-label itself.
    with pytest.raises(ValidationError):
        normalize_source(value)


@pytest.mark.parametrize("case", VECTORS["accept"], ids=lambda case: repr(case["input"])[:60])
def test_normalising_twice_changes_nothing(case):
    value = normalize_source(case["input"])
    assert normalize_source(value) == value


@pytest.mark.parametrize("value", [None, 5, 1.5, [], {}, b"https://example.org/", True])
def test_a_non_string_is_refused(value):
    with pytest.raises(ValidationError) as exc:
        normalize_source(value)
    assert codes(exc) == ["invalid_source"]


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("", "empty_source"),
        ("   \n", "empty_source"),
        ("javascript:alert(1)", "invalid_source"),
        ("https://user:pw@example.org/", "invalid_source"),
        ("http://127.0.0.1/", "invalid_source"),
        ("doi:abc", "invalid_doi"),
        ("10.12/x", "invalid_doi"),
        ("https://example.org/" + "a" * 600, "source_too_long"),
        ("10.1000/" + "a" * 600, "source_too_long"),
        ("https://example.org/" + "a" * 3000, "source_too_long"),
    ],
)
def test_errors_carry_a_code(value, code):
    with pytest.raises(ValidationError) as exc:
        normalize_source(value)
    assert codes(exc) == [code]


def test_credentials_get_their_own_message():
    for value in ["https://user:pw@example.org/", "https://user@example.org/"]:
        with pytest.raises(ValidationError) as exc:
            normalize_source(value)
        assert "username or password" in exc.value.messages[0]


def test_ip_and_localhost_get_their_own_message():
    with pytest.raises(ValidationError) as exc:
        normalize_source("http://localhost:8000/")
    assert "IP addresses and localhost" in exc.value.messages[0]


def test_a_500_character_url_is_fine_and_501_is_not():
    base = "https://example.org/"
    assert len(normalize_source(base + "a" * (500 - len(base)))) == 500
    with pytest.raises(ValidationError):
        normalize_source(base + "a" * (501 - len(base)))


def test_the_length_limit_applies_after_punycode_and_percent_encoding():
    # 150 characters of path, three bytes each once encoded: 450 + the host.
    path = "€" * 150
    with pytest.raises(ValidationError) as exc:
        normalize_source("https://example.org/" + path)
    assert codes(exc) == ["source_too_long"]


def test_a_doi_keeps_its_case():
    assert normalize_source("doi:10.1038/S41558-Abc") == "10.1038/S41558-Abc"


def test_source_kind():
    assert source_kind("10.1000/xyz") == "doi"
    assert source_kind("https://example.org/") == "url"
    assert source_kind("http://example.org/") == "url"


@pytest.mark.parametrize("case", VECTORS["lists"], ids=lambda case: f"{len(case['inputs'])} items")
def test_source_lists(case):
    if "ok" in case:
        assert validate_sources(case["inputs"]) == case["ok"]
        return
    with pytest.raises(ValidationError) as exc:
        validate_sources(case["inputs"])
    if case.get("too_many"):
        assert not hasattr(exc.value, "error_dict")
        assert codes(exc) == ["too_many_sources"]
        return
    assert set(exc.value.error_dict) == set(case["bad"])
    for index, expected in case["bad"].items():
        errors = exc.value.error_dict[index]
        if expected == "invalid":
            assert errors[0].code in {"invalid_source", "invalid_doi", "empty_source"}
        else:
            assert [error.message for error in errors] == [expected]
            assert errors[0].code == "duplicate_source"


def test_five_sources_are_allowed_and_six_are_not():
    five = [f"10.1000/s{i}" for i in range(5)]
    assert validate_sources(five) == five
    with pytest.raises(ValidationError) as exc:
        validate_sources([*five, "10.1000/s5"])
    assert codes(exc) == ["too_many_sources"]


def test_order_is_kept():
    values = ["https://z.example/", "10.1000/a", "https://a.example/"]
    assert validate_sources(values) == values


def test_a_duplicate_across_kinds_is_reported_on_the_later_index():
    with pytest.raises(ValidationError) as exc:
        validate_sources(["https://doi.org/10.1000/xyz", "doi:10.1000/XYZ"])
    assert list(exc.value.error_dict) == ["1"]
    assert exc.value.error_dict["1"][0].code == "duplicate_source"


def test_a_tuple_works_like_a_list():
    assert validate_sources(("10.1000/a",)) == ["10.1000/a"]


@pytest.mark.parametrize("value", ["10.1000/a", None, 5, {"a": 1}])
def test_something_that_is_not_a_list_is_refused(value):
    with pytest.raises(ValidationError) as exc:
        validate_sources(value)
    assert codes(exc) == ["invalid_sources"]


def test_a_non_string_element_is_reported_by_index():
    with pytest.raises(ValidationError) as exc:
        validate_sources(["10.1000/a", 5, None])
    assert set(exc.value.error_dict) == {"1", "2"}
