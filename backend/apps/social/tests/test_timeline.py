"""The mixed timeline's pure parts: the per-page rule (`take_page`), the key and the cursor token.
No database here; `test_timeline_db.py` pages real rows."""

import base64
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from rest_framework.exceptions import NotFound

from apps.social import timeline
from apps.social.timeline import POST, REPOST, ZERO_UUID, Key, decode_token, take_page

BASE = datetime(2026, 10, 10, 12, 0, 0, tzinfo=UTC)
A, B, C, D = (uuid.UUID(int=n) for n in (0xA, 0xB, 0xC, 0xD))
WHO = uuid.UUID(int=0x77)


def rows(*refs):
    """Keys newest first, each one second older than the one before; a `*` marks a repost."""
    out = []
    for i, ref in enumerate(refs):
        repost = ref.startswith("*")
        post = {"A": A, "B": B, "C": C, "D": D}[ref.lstrip("*")]
        at = BASE - timedelta(seconds=i)
        out.append(Key(at, REPOST if repost else POST, post, WHO if repost else ZERO_UUID))
    return out


def refs(keys):
    return [
        {A: "A", B: "B", C: "C", D: "D"}[k.ref] + ("*" if k.kind == REPOST else "") for k in keys
    ]


# ---------- take_page ----------


def test_an_empty_list_is_an_empty_page_with_no_next():
    assert take_page([], 3, dedupe=True) == ([], None)


def test_distinct_posts_fill_the_page_and_the_cursor_is_the_last_one_shown():
    given = rows("A", "B", "C", "D")
    kept, nxt = take_page(given, 2, dedupe=True)
    assert refs(kept) == ["A", "B"]
    assert nxt == given[1]


def test_fewer_rows_than_a_page_have_no_next():
    kept, nxt = take_page(rows("A", "B"), 3, dedupe=True)
    assert refs(kept) == ["A", "B"] and nxt is None


def test_a_repeat_inside_the_window_is_consumed_not_shown():
    kept, nxt = take_page(rows("A", "B", "*A", "C"), 3, dedupe=True)
    assert refs(kept) == ["A", "B", "C"] and nxt is None


def test_the_first_row_of_a_post_wins_whatever_its_kind():
    kept, _ = take_page(rows("*A", "B", "A"), 3, dedupe=True)
    assert refs(kept) == ["A*", "B"]
    kept, _ = take_page(rows("A", "*A"), 3, dedupe=True)
    assert refs(kept) == ["A"]


def test_repeats_after_the_page_is_full_are_consumed_until_a_new_post():
    given = rows("A", "B", "*A", "*B", "C")
    kept, nxt = take_page(given, 2, dedupe=True)
    assert refs(kept) == ["A", "B"]
    assert nxt == given[3]  # the two repeats were consumed; C waits for the next page


def test_a_window_of_one_post_gives_one_item_and_a_cursor_at_row_2n_minus_1():
    given = rows("A", "*A", "*A", "*A", "*A")  # size 2: fetch_limit is 5, the window is 4
    kept, nxt = take_page(given, 2, dedupe=True)
    assert refs(kept) == ["A"]
    assert nxt == given[3]  # the progress guarantee: the cursor moved past the whole window


def test_exactly_the_window_all_walked_has_no_next():
    kept, nxt = take_page(rows("A", "*A", "*A", "*A"), 2, dedupe=True)
    assert refs(kept) == ["A"] and nxt is None


def test_the_probe_row_alone_is_enough_for_a_next():
    given = rows("A", "B", "C")  # size 2: the third row is the probe
    kept, nxt = take_page(given, 2, dedupe=True)
    assert refs(kept) == ["A", "B"] and nxt == given[1]


def test_size_one():
    given = rows("A", "*A", "B")
    kept, nxt = take_page(given, 1, dedupe=True)
    assert refs(kept) == ["A"] and nxt == given[1]
    kept, nxt = take_page(rows("A", "B", "C"), 1, dedupe=True)
    assert refs(kept) == ["A"] and nxt == rows("A")[0]


def test_without_dedupe_the_page_is_the_first_size_rows_and_nothing_is_hidden():
    given = rows("A", "*A", "B", "C")
    kept, nxt = take_page(given, 2, dedupe=False)
    assert refs(kept) == ["A", "A*"] and nxt == given[1]
    kept, nxt = take_page(given[:2], 2, dedupe=False)
    assert nxt is None


def test_fetch_limit_is_the_window_plus_a_probe():
    assert timeline.fetch_limit(20, True) == 41
    assert timeline.fetch_limit(20, False) == 21
    assert timeline.fetch_limit(1, True) == 3


# ---------- the token ----------


def b64(text):
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


@pytest.mark.parametrize("micros", [0, 1, 999_999, 1_760_000_000_000_000, 1_760_000_000_123_456])
@pytest.mark.parametrize("kind", [POST, REPOST])
def test_a_token_round_trips(micros, kind):
    at = timeline.EPOCH + timedelta(microseconds=micros)
    key = Key(at, kind, A, ZERO_UUID if kind == POST else WHO)
    assert key.micros() == micros
    assert decode_token(key.token()) == key
    assert timeline.key_from_cache_row(key.cache_row()) == key


def test_the_token_is_a_bare_url_safe_string():
    token = Key(BASE, REPOST, A, WHO).token()
    assert token.isascii() and "=" not in token and "+" not in token and "/" not in token


def test_microseconds_survive_where_isoformat_would_drop_them():
    plain = Key(BASE, POST, A, ZERO_UUID)  # .000000: isoformat() prints no fraction at all
    assert decode_token(plain.token()).at == BASE


GOOD = f"1760000000000000|1|{A}|{WHO}"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "junk",
        f"1760000000000000|1|{A}",  # three parts
        f"{GOOD}|extra",  # five parts
        f"1760000000000000|2|{A}|{WHO}",  # a kind that doesn't exist
        f"1760000000000000|x|{A}|{WHO}",
        f"-5|1|{A}|{WHO}",
        f"+5|1|{A}|{WHO}",
        f" 5|1|{A}|{WHO}",
        f"01760000000000000|1|{A}|{WHO}",  # leading zero: not what we write
        f"1760000000000000|01|{A}|{WHO}",
        f"1760000000000000|1|{str(A).upper()}|{WHO}",  # not canonical
        f"1760000000000000|1|{A.hex}|{WHO}",
        f"1760000000000000|1|not-a-uuid|{WHO}",
        f"1760000000000000|0|{A}|{WHO}",  # a post item with a reposter
        f"{'9' * 40}|1|{A}|{WHO}",  # overflows a datetime
        f"{'9' * 18}|1|{A}|{WHO}",  # year beyond 9999
        f"١٢٣|1|{A}|{WHO}",  # Arabic-Indic digits
    ],
)
def test_a_crafted_token_is_a_404(text):
    with pytest.raises(NotFound):
        decode_token(b64(text))


@pytest.mark.parametrize("token", ["!!!", "====", "é", "cD1ub3QtYS1kYXRl", GOOD])
def test_a_token_that_is_not_ours_is_a_404(token):
    with pytest.raises(NotFound):
        decode_token(token)


def test_padding_or_junk_characters_are_not_a_cursor_either():
    token = Key(BASE, POST, A, ZERO_UUID).token()
    for variant in (token + "=", token + "!!", "!" + token, token[:-1] + "\n"):
        with pytest.raises(NotFound):
            decode_token(variant)


def test_non_ascii_bytes_are_a_404():
    with pytest.raises(NotFound):
        decode_token(base64.urlsafe_b64encode("é|1|a|b".encode()).decode())


@pytest.mark.parametrize(
    "row",
    [
        None,
        "x",
        [],
        [1, 0, str(A)],
        [1, 0, str(A), str(ZERO_UUID), 1],
        [True, 0, str(A), str(ZERO_UUID)],
        [1, True, str(A), str(ZERO_UUID)],
        [-1, 0, str(A), str(ZERO_UUID)],
        [1.5, 0, str(A), str(ZERO_UUID)],
        [1, 2, str(A), str(ZERO_UUID)],
        [1, [0], str(A), str(ZERO_UUID)],
        [1, 0, 7, str(ZERO_UUID)],
        [1, 0, str(A), str(A)],
        [10**30, 0, str(A), str(ZERO_UUID)],
    ],
)
def test_a_malformed_cache_row_is_refused(row):
    assert timeline.key_from_cache_row(row) is None
