"""Reconciliation pipeline step: merge per-source extractions into one grounded record."""

import logging

logger = logging.getLogger(__name__)

_TRUST_TIER_SCORES: dict[str, float] = {
    "official": 1.0,
    "directory": 0.6,
    "news": 0.5,
    "unknown": 0.3,
}

# Fields that are arrays of groundedStrings (not single groundedString objects)
_ARRAY_FIELDS = {"materials_produced", "certifications"}

# Fields to skip during reconciliation (handled separately or not reconciled)
_SKIP_FIELDS = {"location_verification", "_metrics"}


class ReconcilerStep:
    """Merges extraction results from multiple sources into a single grounded record.

    For each scalar field, all candidate values are scored by multiplying the
    source's trust tier score by the extraction confidence. The highest-scoring
    candidate wins. For array fields, all unique values across sources are merged.

    All decisions are written to ``provenance.reconciliations`` for auditability.

    Trust tier scores:
        - official:   1.0
        - directory:  0.6
        - news:       0.5
        - unknown:    0.3
    """

    def run(self, extractions: list[dict], sources: list[dict]) -> dict:
        """Merge per-source extraction dicts into a single reconciled record.

        Args:
            extractions: List of partial extraction dicts, one per scraped page.
                         Each dict may contain groundedString fields and a
                         ``_metrics`` key.
            sources:     List of source metadata dicts (source_id, trust_tier,
                         url, fetched_at, content_hash) in the same order as
                         extractions.

        Returns:
            Dict with keys:
            - ``extraction``: reconciled field values
            - ``reconciliations``: list of reconciliation records for provenance
        """
        if not extractions:
            return {"extraction": {}, "reconciliations": []}

        all_fields = set()
        for ext in extractions:
            all_fields.update(k for k in ext if k not in _SKIP_FIELDS)

        reconciled: dict = {}
        reconciliations: list[dict] = []

        for field in all_fields:
            if field in _ARRAY_FIELDS:
                reconciled[field] = self._merge_array_field(
                    field, extractions, sources, reconciliations
                )
            else:
                reconciled[field] = self._reconcile_scalar_field(
                    field, extractions, sources, reconciliations
                )

        # Preserve location_verification from the most trusted source that has it
        for ext, _src in zip(extractions, sources, strict=False):
            if "location_verification" in ext and ext["location_verification"]:
                reconciled["location_verification"] = ext["location_verification"]
                break

        return {"extraction": reconciled, "reconciliations": reconciliations}

    def _reconcile_scalar_field(
        self,
        field: str,
        extractions: list[dict],
        sources: list[dict],
        reconciliations: list[dict],
    ) -> dict:
        """Pick the best single value for a scalar groundedString field."""
        candidates = []

        for ext, src in zip(extractions, sources, strict=False):
            grounded = ext.get(field)
            if not grounded or not isinstance(grounded, dict):
                continue

            value = grounded.get("value")
            confidence = grounded.get("confidence", 0.0)
            trust_score = _TRUST_TIER_SCORES.get(src.get("trust_tier", "unknown"), 0.3)
            score = confidence * trust_score

            candidates.append(
                {
                    "value": value,
                    "source_id": src["source_id"],
                    "score": round(score, 4),
                    "grounded": grounded,
                }
            )

        if not candidates:
            return {
                "value": None,
                "confidence": 0.0,
                "evidence": [],
                "abstain_reason": "no_evidence",
            }

        # Sort by score descending — highest-scoring value wins
        candidates.sort(key=lambda c: c["score"], reverse=True)
        winner = candidates[0]

        # Only log a reconciliation when there were multiple competing values
        non_null = [c for c in candidates if c["value"] is not None]
        if len(non_null) > 1:
            reason = (
                f"Highest trust×confidence score: {winner['source_id']} "
                f"(score={winner['score']:.3f})"
            )
            reconciliations.append(
                {
                    "field": field,
                    "candidates": [
                        {"value": c["value"], "source_id": c["source_id"], "score": c["score"]}
                        for c in candidates
                    ],
                    "winner_source_id": winner["source_id"],
                    "reason": reason,
                }
            )
            logger.debug("Reconciled %s → %r (score=%.3f)", field, winner["value"], winner["score"])

        return winner["grounded"]

    def _merge_array_field(
        self,
        field: str,
        extractions: list[dict],
        sources: list[dict],
        reconciliations: list[dict],
    ) -> list[dict]:
        """Merge array fields by collecting all unique non-null values across sources."""
        seen_values: set[str] = set()
        merged: list[dict] = []

        for ext, _src in zip(extractions, sources, strict=False):
            items = ext.get(field, [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                value = item.get("value")
                if value and value.lower() not in seen_values:
                    seen_values.add(value.lower())
                    merged.append(item)

        return merged
