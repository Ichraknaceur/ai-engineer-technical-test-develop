"""Provider-agnostic LLM extractor for grounded quarry field extraction.

The extractor is decoupled from any specific LLM provider. Pass any object
that satisfies the ILLMProvider protocol (OpenAI, Claude, Mistral, etc.).
The default provider is OpenAI gpt-4o.

Usage:
    extractor = LLMExtractor()                          # default: OpenAI gpt-4o
    extractor = LLMExtractor(provider=ClaudeProvider()) # swap to Claude
    result = await extractor.extract(page)
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

from backend.domain.entities.source import ScrapedPage

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "site_schema.json"

_SYSTEM_PROMPT = """You are a structured data extraction engine for industrial quarry sites.

Your task: extract quarry metadata from the provided web page text and return a JSON object.

Rules:
1. GROUNDING: Every non-null value MUST include at least one evidence entry with:
   - source_id: the page's source_id
   - char_start / char_end: character offsets of the supporting quote in the text
   - quote: the verbatim text slice

2. ABSTENTION: If you cannot find reliable evidence for a field, set value=null and
   provide an abstain_reason. Valid reasons:
   - "no_evidence": field not mentioned in the text
   - "insufficient_evidence": mentioned but too vague or ambiguous
   - "stale_evidence": only outdated information found (no date or date > 3 years ago)
   - "contradictory_evidence": multiple conflicting values found

3. CONFIDENCE: Score in [0.0, 1.0]:
   - 0.9-1.0: explicit, recent, unambiguous statement
   - 0.6-0.9: implicit but reasonably clear
   - 0.3-0.6: uncertain or indirect
   - 0.0-0.3: very weak or stale

4. NEVER invent values. A confident wrong answer is worse than no answer.

5. operational_status values: "active", "inactive", "unknown" — or null if abstaining.

Return ONLY valid JSON matching the extraction schema. No prose, no markdown fences."""

_USER_PROMPT_TEMPLATE = """Source ID: {source_id}
URL: {url}
Trust tier: {trust_tier}

--- PAGE TEXT ---
{text}
--- END ---

Extract the following fields. ALL fields are optional — abstain (value=null) if evidence is missing.

SCALAR fields (return a single groundedString object):
- official_name: The official legal or commercial name of the quarry
- site_type: Always "Quarry" if confirmed, else null
- description: Brief description of the site and its activities
- operational_status: "active", "inactive", or null

ARRAY fields (return a JSON array of groundedString objects, or [] if none found):
- materials_produced: Each material as a separate groundedString (limestone, granite, sand...)
- certifications: Each certification as a separate groundedString (ISO 14001, CE marking...)

OBJECT field:
- location_verification: {{"is_verified": bool, "confidence": float, "extracted_city": str|null, "method": "string_match"|"geocode"|"llm_inference"|"none"}}

Return a single JSON object with exactly these keys."""


def _prompt_hash(prompt: str) -> str:
    """Return a short SHA-256 of the system prompt for run_metadata traceability."""
    return "sha256:" + hashlib.sha256(prompt.encode()).hexdigest()[:16]


@runtime_checkable
class ILLMProvider(Protocol):
    """Protocol that any LLM provider must satisfy.

    A provider wraps a single model API and handles authentication,
    token counting, and cost estimation. The extractor is unaware of
    which underlying LLM is being used.
    """

    model: str

    async def complete(self, system_prompt: str, user_prompt: str) -> tuple[str, int, int, float]:
        """Send a completion request and return usage metadata.

        Args:
            system_prompt: Extraction instructions.
            user_prompt:   Page content + field definitions.

        Returns:
            Tuple of (raw_json_string, tokens_in, tokens_out, usd_cost).
        """
        ...


class LLMExtractor:
    """Extracts grounded quarry metadata from a scraped page using any LLM provider.

    The provider is injected at construction time. Swap the provider to change
    the underlying model without touching extraction logic.

    Args:
        provider: An object satisfying ILLMProvider. Defaults to OpenAI gpt-4o.
    """

    def __init__(self, provider: ILLMProvider | None = None) -> None:
        if provider is None:
            from backend.infrastructure.llm.providers.openai_provider import OpenAIProvider

            provider = OpenAIProvider()
        self._provider = provider
        self._prompt_hash = _prompt_hash(_SYSTEM_PROMPT)

    async def extract(self, page: ScrapedPage) -> dict:
        """Extract grounded fields from a scraped page.

        If the page has an error or empty text, returns a fully-abstained
        extraction without calling the LLM.

        Args:
            page: A ScrapedPage produced by HttpScraper.

        Returns:
            Partial extraction dict where each field follows the groundedString
            schema. Includes a ``_metrics`` key with token counts, cost, and
            latency.
        """
        if page.error or not page.cleaned_text.strip():
            return _abstain_all(
                self._provider.model, self._prompt_hash, reason="empty_or_errored_page"
            )

        user_prompt = _USER_PROMPT_TEMPLATE.format(
            source_id=page.source_id,
            url=page.url,
            trust_tier=page.trust_tier,
            text=page.cleaned_text,
        )

        t0 = time.monotonic()
        try:
            raw, tokens_in, tokens_out, cost = await self._provider.complete(
                _SYSTEM_PROMPT, user_prompt
            )
        except Exception as exc:
            logger.error(
                "LLM provider %s failed for %s: %s — type: %s",
                self._provider.model,
                page.url,
                exc,
                type(exc).__name__,
            )
            return _abstain_all(self._provider.model, self._prompt_hash, reason="llm_api_error")

        latency_ms = int((time.monotonic() - t0) * 1000)

        try:
            extraction = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse LLM JSON response for %s: %s", page.url, exc)
            return _abstain_all(self._provider.model, self._prompt_hash, reason="llm_invalid_json")

        extraction["_metrics"] = {
            "model": self._provider.model,
            "purpose": "field_extraction",
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "usd_cost": cost,
            "latency_ms": latency_ms,
            "prompt_hash": self._prompt_hash,
        }

        logger.info(
            "Extracted fields from %s via %s — %d tokens, $%.4f",
            page.url,
            self._provider.model,
            tokens_in + tokens_out,
            cost,
        )
        return extraction


def _abstain_all(model: str, prompt_hash: str, reason: str) -> dict:
    """Return a fully-abstained extraction dict for all fields.

    Args:
        model:       The model name for metrics tracking.
        prompt_hash: Hash of the system prompt used.
        reason:      Machine-readable abstention reason.

    Returns:
        Extraction dict with all fields set to null + abstain_reason.
    """
    abstained = {"value": None, "confidence": 0.0, "evidence": [], "abstain_reason": reason}
    return {
        "official_name": abstained,
        "site_type": abstained,
        "description": abstained,
        "materials_produced": [],
        "certifications": [],
        "operational_status": abstained,
        "_metrics": {
            "model": model,
            "purpose": "field_extraction",
            "tokens_in": 0,
            "tokens_out": 0,
            "usd_cost": 0.0,
            "latency_ms": 0,
            "prompt_hash": prompt_hash,
        },
    }
