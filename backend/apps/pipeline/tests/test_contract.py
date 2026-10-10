"""The pipeline contract (ARCHITECTURE §6): what may be built, and what is refused."""

import uuid
from decimal import Decimal

import pytest

from apps.pipeline.contract import ContractError, PipelineRequest, PipelineResult

POST_ID = uuid.UUID("2f0a6c1e-1b6b-4d2a-9c3e-5a7f8e9d0b1c")


# ---------- PipelineRequest ----------


def test_a_request_carries_the_post_its_text_and_its_sources_in_order():
    request = PipelineRequest(
        POST_ID, "Water boils at 100 °C at sea level.", ("10.1/x", "https://a.b")
    )
    assert request.to_json() == {
        "post_id": str(POST_ID),
        "content": "Water boils at 100 °C at sea level.",
        "sources": ["10.1/x", "https://a.b"],
    }


def test_a_request_without_sources_sends_an_empty_list():
    assert PipelineRequest(POST_ID, "Claim").to_json()["sources"] == []


def test_for_post_keeps_the_stored_order():
    class Post:
        pk = POST_ID
        content = "Claim"
        sources = ["https://z.example", "10.1000/a", "https://a.example"]

    request = PipelineRequest.for_post(Post())
    assert request.sources == ("https://z.example", "10.1000/a", "https://a.example")


def test_a_request_is_frozen():
    request = PipelineRequest(POST_ID, "Claim")
    with pytest.raises(AttributeError):
        request.content = "Other"


@pytest.mark.parametrize(
    ("post_id", "content", "sources"),
    [
        (str(POST_ID), "Claim", ()),  # a string is not a UUID
        (POST_ID, "", ()),
        (POST_ID, "x" * 501, ()),
        (POST_ID, None, ()),
        (POST_ID, "Claim", ["https://a.example"]),  # a list is refused, not copied
        (POST_ID, "Claim", ("https://a.example",) * 6),
        (POST_ID, "Claim", ("",)),
        (POST_ID, "Claim", ("x" * 501,)),
        (POST_ID, "Claim", (None,)),
    ],
)
def test_a_request_that_breaks_the_contract_is_refused(post_id, content, sources):
    with pytest.raises(ContractError):
        PipelineRequest(post_id, content, sources)


def test_content_is_counted_in_code_points():
    assert PipelineRequest(POST_ID, "😀" * 500).content == "😀" * 500
    with pytest.raises(ContractError):
        PipelineRequest(POST_ID, "😀" * 501)


# ---------- PipelineResult ----------


@pytest.mark.parametrize(
    ("given", "stored"),
    [
        (Decimal("95"), Decimal("95.00")),
        (95, Decimal("95.00")),
        ("92.5", Decimal("92.50")),
        (" 40 ", Decimal("40.00")),
        (0, Decimal("0.00")),
        ("-0", Decimal("0.00")),
        (100, Decimal("100.00")),
        ("1e2", Decimal("100.00")),
        (Decimal("84.995"), Decimal("85.00")),  # half up, then compared with the threshold
        (Decimal("84.994"), Decimal("84.99")),
        (Decimal("99.995"), Decimal("100.00")),
    ],
)
def test_the_confidence_is_kept_to_two_places_rounded_half_up(given, stored):
    result = PipelineResult("true", given, {})
    assert result.confidence_score == stored
    assert str(result.confidence_score) == str(stored)


@pytest.mark.parametrize(
    "score",
    [
        True,  # bool is an int in Python
        95.0,  # a float doesn't say exactly what it means
        None,
        "",
        "high",
        "NaN",
        "Infinity",
        Decimal("NaN"),
        Decimal("-0.001"),  # the range is checked on the exact value, before rounding
        Decimal("100.001"),
        -1,
        101,
        [95],
    ],
)
def test_a_confidence_outside_0_to_100_or_of_the_wrong_type_is_refused(score):
    with pytest.raises(ContractError, match="confidence_score"):
        PipelineResult("true", score, {})


@pytest.mark.parametrize("verdict", ["TRUE", "True", "yes", "", None, True, "debunked"])
def test_only_the_three_verdicts_exist(verdict):
    with pytest.raises(ContractError, match="verdict"):
        PipelineResult(verdict, 90, {})


@pytest.mark.parametrize("verdict", ["true", "false", "inconclusive"])
def test_each_verdict_is_accepted(verdict):
    assert PipelineResult(verdict, 50, {"a": 1}).verdict == verdict


@pytest.mark.parametrize("raw", [None, [], "text", 1])
def test_the_raw_result_must_be_an_object(raw):
    with pytest.raises(ContractError, match="raw_result"):
        PipelineResult("true", 90, raw)


def test_from_json_reads_the_three_keys_and_ignores_others():
    payload = {
        "verdict": "false",
        "confidence_score": 91.5,
        "raw_result": {"model": "x", "evidence": [1, 2]},
        "extra": "ignored",
    }
    result = PipelineResult.from_json(payload)
    assert result == PipelineResult("false", Decimal("91.50"), {"model": "x", "evidence": [1, 2]})


def test_from_json_turns_a_float_into_a_decimal_through_its_text():
    # Decimal(0.1 + 0.2) would be 0.3000000000000000444…; through str it is exactly 0.30.
    assert PipelineResult.from_json(
        {"verdict": "true", "confidence_score": 0.1 + 0.2, "raw_result": {}}
    ).confidence_score == Decimal("0.30")


@pytest.mark.parametrize(
    "payload",
    [
        [],
        "true",
        None,
        {"confidence_score": 90, "raw_result": {}},
        {"verdict": "true", "raw_result": {}},
        {"verdict": "true", "confidence_score": 90},
        {"verdict": "true", "confidence_score": float("nan"), "raw_result": {}},
    ],
)
def test_from_json_refuses_a_malformed_answer(payload):
    with pytest.raises(ContractError):
        PipelineResult.from_json(payload)
