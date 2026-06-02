"""Reconciliation pipeline step: merge per-source extractions into one grounded record."""


class ReconcilerStep:
    """Merges extraction results from multiple sources into a single grounded record.

    For each field, all candidate values are scored by multiplying the source's
    trust tier score by the extraction confidence. The highest-scoring candidate
    wins. All candidates and the winner's reason are written to
    ``provenance.reconciliations`` so the decision is fully auditable.

    Trust tier scores:
        - official:   1.0
        - directory:  0.6
        - news:       0.5
        - unknown:    0.3
    """

    def run(self, extractions: list[dict], sources: list[dict]) -> dict:
        """Merge per-source extraction dicts into a single reconciled extraction dict.

        Args:
            extractions: List of partial extraction dicts, one per scraped page.
            sources:     List of source metadata dicts (source_id, trust_tier, etc.)
                         in the same order as extractions.

        Returns:
            A reconciled extraction dict with provenance.reconciliations populated.
        """
        raise NotImplementedError
