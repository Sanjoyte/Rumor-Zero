"""The bounded offset helper behind search (Part 12): every cursor, the one-row look-ahead."""

import pytest
from rest_framework.exceptions import NotFound
from rest_framework.test import APIRequestFactory

from apps.core.pagination import offset_page_number, paginate_offset


def request_with(cursor=None):
    params = {} if cursor is None else {"cursor": cursor}
    # `query_params` is what DRF's Request exposes; a plain Django request has `GET`.
    request = APIRequestFactory().get("/", params)
    request.query_params = request.GET
    return request


@pytest.mark.parametrize("cursor", [None, ""])
def test_a_missing_or_empty_cursor_is_page_one(cursor):
    assert offset_page_number(request_with(cursor)) == 1


@pytest.mark.parametrize("number", [2, 3, 4, 5])
def test_pages_two_to_five_are_accepted(number):
    assert offset_page_number(request_with(str(number))) == number


@pytest.mark.parametrize("cursor", ["1", "0", "6", "02", "abc", " ", "-1", "2.0", "٢", "5 "])
def test_any_other_cursor_is_a_404(cursor):
    with pytest.raises(NotFound) as caught:
        offset_page_number(request_with(cursor))
    assert str(caught.value.detail) == "Invalid cursor"


def test_the_cap_is_a_parameter():
    assert offset_page_number(request_with("3"), max_pages=3) == 3
    with pytest.raises(NotFound):
        offset_page_number(request_with("4"), max_pages=3)


def test_a_full_page_with_one_more_row_has_a_next_page():
    rows, next_cursor = paginate_offset(list(range(21)), request_with(), page_size=20)
    assert rows == list(range(20))
    assert next_cursor == "2"


def test_exactly_a_full_page_has_no_next_page():
    rows, next_cursor = paginate_offset(list(range(20)), request_with(), page_size=20)
    assert len(rows) == 20 and next_cursor is None


def test_later_pages_start_where_the_previous_ended():
    data = list(range(45))
    rows, next_cursor = paginate_offset(data, request_with("2"), page_size=20)
    assert rows == list(range(20, 40)) and next_cursor == "3"
    rows, next_cursor = paginate_offset(data, request_with("3"), page_size=20)
    assert rows == list(range(40, 45)) and next_cursor is None


def test_the_last_allowed_page_never_points_further():
    rows, next_cursor = paginate_offset(list(range(500)), request_with("5"), page_size=20)
    assert rows == list(range(80, 100))
    assert next_cursor is None


def test_a_page_past_the_end_is_empty():
    rows, next_cursor = paginate_offset(list(range(3)), request_with("2"), page_size=20)
    assert rows == [] and next_cursor is None
