"""The fixed fact-check pipeline contract (ARCHITECTURE §6; guide §7.1; ANALYSIS c-27).

Frozen dataclasses, validated when they are built, so a request or a result that exists is a good
one. Swapping the stub for a real pipeline changes nothing on this side of the contract.
"""

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from apps.posts.models import MAX_CONTENT_LENGTH, MAX_SOURCE_LENGTH, MAX_SOURCES

VERDICTS = ("true", "false", "inconclusive")
_CENT = Decimal("0.01")


class ContractError(ValueError):
    """A request or a result that breaks the contract. The message is ours, never a value."""


@dataclass(frozen=True)
class PipelineRequest:
    """What the pipeline is asked about one fact post. `sources` (0–5 URLs or DOIs, in the order
    the author entered them) is for the real pipeline; we never fetch them (§4c)."""

    post_id: uuid.UUID
    content: str
    sources: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.post_id, uuid.UUID):
            raise ContractError("post_id must be a UUID")
        if not isinstance(self.content, str) or not 1 <= len(self.content) <= MAX_CONTENT_LENGTH:
            raise ContractError(f"content must be 1 to {MAX_CONTENT_LENGTH} characters")
        # A tuple, so a request can't change after it was built (a list is refused, not copied).
        if not isinstance(self.sources, tuple) or len(self.sources) > MAX_SOURCES:
            raise ContractError(f"sources must be a tuple of at most {MAX_SOURCES} strings")
        for source in self.sources:
            if not isinstance(source, str) or not 1 <= len(source) <= MAX_SOURCE_LENGTH:
                raise ContractError(f"each source must be 1 to {MAX_SOURCE_LENGTH} characters")

    @classmethod
    def for_post(cls, post):
        return cls(post_id=post.pk, content=post.content, sources=tuple(post.sources))

    def to_json(self):
        return {
            "post_id": str(self.post_id),
            "content": self.content,
            "sources": list(self.sources),
        }


def _confidence(value):
    """A score of 0–100 as a Decimal with two places. The range is checked on the exact value,
    then it is rounded half up (what is stored, shown and compared with the threshold)."""
    # bool is an int in Python, and a float can't say what it means exactly: both are refused
    # (`from_json` turns a JSON number into a Decimal through its text first).
    if isinstance(value, bool) or not isinstance(value, Decimal | int | str):
        raise ContractError("confidence_score must be a number from 0 to 100")
    try:
        number = Decimal(value.strip() if isinstance(value, str) else value)
    except InvalidOperation:
        raise ContractError("confidence_score must be a number from 0 to 100") from None
    if not number.is_finite() or not 0 <= number <= 100:
        raise ContractError("confidence_score must be a number from 0 to 100")
    rounded = number.quantize(_CENT, rounding=ROUND_HALF_UP)
    return rounded.copy_abs() if rounded.is_zero() else rounded  # never "-0.00"


@dataclass(frozen=True)
class PipelineResult:
    """The pipeline's answer. `raw_result` is kept verbatim in `posts.pipeline_result`."""

    verdict: str
    confidence_score: Decimal
    raw_result: dict

    def __post_init__(self):
        if not isinstance(self.verdict, str) or self.verdict not in VERDICTS:
            raise ContractError(f"verdict must be one of: {', '.join(VERDICTS)}")
        object.__setattr__(self, "confidence_score", _confidence(self.confidence_score))
        if not isinstance(self.raw_result, dict):
            raise ContractError("raw_result must be an object")

    @classmethod
    def from_json(cls, payload):
        """Build a result from a decoded JSON answer. Keys other than the three are ignored."""
        if not isinstance(payload, dict):
            raise ContractError("the answer must be a JSON object")
        missing = [
            key for key in ("verdict", "confidence_score", "raw_result") if key not in payload
        ]
        if missing:
            raise ContractError(f"the answer lacks: {', '.join(missing)}")
        score = payload["confidence_score"]
        if isinstance(score, float):
            score = Decimal(str(score))  # the shortest text that round-trips, e.g. 95.5
        return cls(
            verdict=payload["verdict"],
            confidence_score=score,
            raw_result=payload["raw_result"],
        )
