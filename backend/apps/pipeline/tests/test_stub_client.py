"""The deterministic stub (ARCHITECTURE §6): the tags, the hash rule, and nothing else."""

import random
import string
import uuid
from decimal import Decimal

import pytest

from apps.pipeline.clients import StubPipelineClient
from apps.pipeline.contract import PipelineRequest

POST_ID = uuid.uuid4()


def check(content, sources=()):
    return StubPipelineClient().check(PipelineRequest(POST_ID, content, tuple(sources)))


@pytest.mark.parametrize(
    ("content", "verdict", "confidence", "rule"),
    [
        ("Paris is the capital of France #true", "true", "95.00", "#true"),
        ("The Earth is flat #false", "false", "92.00", "#false"),
        ("Coffee stunts your growth #unsure", "inconclusive", "40.00", "#unsure"),
    ],
)
def test_each_tag_gives_its_fixed_answer(content, verdict, confidence, rule):
    result = check(content)
    assert result.verdict == verdict
    assert result.confidence_score == Decimal(confidence)
    assert result.raw_result == {"stub": True, "rule": rule}


@pytest.mark.parametrize(
    "content", ["#TRUE", "#True.", "(#true)", "x#true", "#true!", "first line\n#true", "#true_"]
)
def test_a_tag_matches_in_any_case_as_a_whole_tag(content):
    expected = "hash" if content == "#true_" else "#true"  # "_" is part of a word
    assert check(content).raw_result["rule"] == expected


@pytest.mark.parametrize("content", ["#trueish", "#true1", "# true", "true", "#truth", "#unsures"])
def test_text_that_only_looks_like_a_tag_falls_to_the_hash_rule(content):
    assert check(content).raw_result == {"stub": True, "rule": "hash"}


@pytest.mark.parametrize(
    ("content", "rule"),
    [
        ("#false, not #true", "#false"),
        ("#true, not #false", "#true"),
        ("#unsure about #true", "#unsure"),
        ("#trueish but #false", "#false"),
    ],
)
def test_the_first_tag_in_the_text_decides(content, rule):
    assert check(content).raw_result["rule"] == rule


@pytest.mark.parametrize(
    ("content", "verdict", "confidence"),
    [
        # Pinned so the rule can't drift: 50 + (bytes 0-1 of SHA-256) % 50, true if byte 2 is even.
        ("The Eiffel Tower is in Paris.", "false", "74.00"),
        ("Honey never spoils.", "true", "88.00"),
        ("Sharks are older than trees.", "false", "95.00"),
        ("The Moon orbits the Earth.", "true", "65.00"),
        ("x", "true", "83.00"),
    ],
)
def test_untagged_text_gets_a_verdict_and_confidence_from_its_sha256(content, verdict, confidence):
    result = check(content)
    assert (result.verdict, result.confidence_score) == (verdict, Decimal(confidence))
    assert result.raw_result == {"stub": True, "rule": "hash"}


def test_the_answer_is_the_same_every_time_and_for_every_client():
    content = "The Great Wall of China is visible from space."
    first = check(content)
    assert all(check(content) == first for _ in range(20))
    assert StubPipelineClient().check(PipelineRequest(uuid.uuid4(), content)) == first


def test_sources_are_ignored():
    content = "Bananas are berries."
    assert check(content) == check(content, ["https://example.org/a", "10.1000/xyz"])
    assert check("#false", ["https://example.org/true"]).verdict == "false"


def test_the_hash_rule_stays_between_50_and_99_and_gives_both_verdicts():
    rng = random.Random(9)
    seen = set()
    for _ in range(1000):
        text = "".join(rng.choices(string.ascii_letters + " ", k=rng.randint(1, 80)))
        result = check(text)
        if result.raw_result["rule"] != "hash":
            continue
        assert Decimal(50) <= result.confidence_score <= Decimal(99)
        assert result.confidence_score == result.confidence_score.to_integral_value()
        seen.add(result.verdict)
    assert seen == {"true", "false"}


def test_the_stub_never_takes_time():
    assert StubPipelineClient.max_seconds == 0
