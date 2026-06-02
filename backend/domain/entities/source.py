"""Source entities representing scraped web pages and their extracted grounded fields."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

TrustTier = Literal["official", "directory", "news", "unknown"]
"""Reliability tier assigned to a source URL.

- ``official``:   The operator's own domain.
- ``directory``:  Industry registries or aggregators (e.g. BRGM, annuaire).
- ``news``:       Press articles mentioning the site.
- ``unknown``:    Any source that does not match the other tiers.
"""


@dataclass
class ScrapedPage:
    """The cleaned content of a fetched web page, ready for LLM extraction.

    Attributes:
        source_id:    SHA-256 of the URL, used as a stable reference in evidence quotes.
        url:          The original URL that was fetched.
        fetched_at:   UTC timestamp of the HTTP request.
        content_hash: SHA-256 of the raw HTML, used for deduplication across jobs.
        cleaned_text: Plain text extracted from the HTML, truncated to 8 000 tokens.
        trust_tier:   Reliability classification of the source domain.
        error:        Non-None if the fetch or cleaning step failed; extraction is skipped.
    """

    source_id: str
    url: str
    fetched_at: datetime
    content_hash: str
    cleaned_text: str
    trust_tier: TrustTier = "unknown"
    error: str | None = None


@dataclass
class GroundedField:
    """An extracted field value paired with the evidence that supports it.

    When the model cannot find reliable evidence, `value` is None and
    `abstain_reason` explains why. Both outcomes are valid and expected.

    Attributes:
        value:          The extracted string, or None when abstaining.
        confidence:     Model certainty in [0.0, 1.0].
        evidence:       List of evidence dicts with source_id, char_start, char_end, quote.
        abstain_reason: Machine-readable reason for abstention (e.g. "no_recent_evidence").
    """

    value: str | None
    confidence: float
    evidence: list[dict] = field(default_factory=list)
    abstain_reason: str | None = None
