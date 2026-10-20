"""Query cleaning for post search (Part 12): pure functions, no database."""

import pytest

from apps.posts.search import (
    MAX_QUERY_LENGTH,
    QueryTooLong,
    clean_post_query,
    has_positive_term,
    strip_control_characters,
)


def test_controls_are_removed_and_whitespace_controls_become_spaces():
    assert strip_control_characters("a\x00b\x7fc\x1bd") == "abcd"
    assert strip_control_characters("a\tb\nc\rd") == "a b c d"


def test_a_lone_surrogate_is_dropped():
    assert strip_control_characters("a\ud800b") == "ab"


def test_the_query_is_trimmed():
    assert clean_post_query("  storm warning \n") == "storm warning"


def test_blank_and_control_only_queries_are_empty():
    assert clean_post_query("") == ""
    assert clean_post_query(" \t\n ") == ""
    assert clean_post_query("\x00\x00") == ""


def test_two_hundred_code_points_are_allowed_and_one_more_is_not():
    assert clean_post_query("x" * MAX_QUERY_LENGTH) == "x" * MAX_QUERY_LENGTH
    with pytest.raises(QueryTooLong):
        clean_post_query("x" * (MAX_QUERY_LENGTH + 1))


def test_the_length_counts_code_points_after_cleaning():
    assert clean_post_query("\x00" * 300 + "ok") == "ok"
    assert clean_post_query("😀" * MAX_QUERY_LENGTH) == "😀" * MAX_QUERY_LENGTH


@pytest.mark.parametrize(
    "query",
    ["storm", "storm warning", '"exact phrase"', "storm -rain", "storm or rain", "a -b c", "-x y"],
)
def test_a_query_with_a_positive_term_is_searched(query):
    assert has_positive_term(query)


@pytest.mark.parametrize(
    "query", ["-foo", "-foo -bar", "or", "or or", "-foo or -bar", '-"a phrase"', "-", "!!!", "   "]
)
def test_a_query_with_no_positive_term_is_not(query):
    assert not has_positive_term(query)


def test_a_quoted_phrase_is_positive_even_when_it_starts_with_a_dash_inside():
    assert has_positive_term('"-foo"')


def test_a_term_in_any_script_counts():
    assert has_positive_term("日本語")
    assert has_positive_term("привет")
