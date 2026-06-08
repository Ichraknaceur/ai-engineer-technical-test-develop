"""Evaluation CLI: score the LLM extractor against the ground-truth set.

Usage:
    python tests/eval/score.py            # live extraction (needs OPENAI_API_KEY)
    python tests/eval/score.py --mock     # offline self-test of the scoring harness

The live mode runs the real extractor on each fixed ground-truth text excerpt,
so results reflect actual model behaviour while staying reproducible (no live
web variance). The mock mode returns the expected values verbatim — useful to
verify the report format and metric maths without an API key or cost.
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Allow running as a standalone script: add the repo root to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.domain.entities.source import ScrapedPage  # noqa: E402
from tests.eval.scorer import aggregate, score_record  # noqa: E402

_GROUND_TRUTH = Path(__file__).parent / "ground_truth.json"


def _load_ground_truth() -> list[dict]:
    data = json.loads(_GROUND_TRUTH.read_text())
    return data["entries"]


def _page_for(entry: dict) -> ScrapedPage:
    """Build a ScrapedPage from a ground-truth text excerpt."""
    return ScrapedPage(
        source_id=entry["source_id"],
        url=f"https://eval.local/{entry['id']}",
        fetched_at=datetime.now(UTC),
        content_hash="sha256:eval",
        cleaned_text=entry["source_text"],
        trust_tier="official",
        error=None,
    )


def _mock_extraction(entry: dict) -> dict:
    """Return a perfect extraction from the expected values (harness self-test)."""
    exp = entry["expected"]

    def grounded(value):
        if value is None:
            return {
                "value": None,
                "confidence": 0.0,
                "evidence": [],
                "abstain_reason": "no_evidence",
            }
        return {
            "value": value,
            "confidence": 0.9,
            "evidence": [
                {"source_id": entry["source_id"], "char_start": 0, "char_end": 1, "quote": "x"}
            ],
            "abstain_reason": None,
        }

    return {
        "official_name": grounded(exp.get("official_name")),
        "site_type": grounded(exp.get("site_type")),
        "operational_status": grounded(exp.get("operational_status")),
        "description": grounded(None),
        "materials_produced": [grounded(m) for m in exp.get("materials_produced", [])],
        "certifications": [],
    }


async def _run(mock: bool) -> int:
    entries = _load_ground_truth()
    scores = []

    if mock:
        for entry in entries:
            scores.append(score_record(entry, _mock_extraction(entry)))
    else:
        from backend.infrastructure.llm.llm_extractor import LLMExtractor

        extractor = LLMExtractor()
        for entry in entries:
            extraction = await extractor.extract(_page_for(entry))
            extraction.pop("_metrics", None)
            scores.append(score_record(entry, extraction))

    _print_report(aggregate(scores), mock)
    return 0


def _print_report(agg, mock: bool) -> None:
    mode = "MOCK (harness self-test)" if mock else "LIVE (OpenAI gpt-4o)"
    print("\n" + "=" * 64)
    print(f"  QUARRY EXTRACTION EVAL — {mode}")
    print("=" * 64)

    print(f"\n  Records scored: {agg.count}\n")
    print("  Per-record:")
    print(f"  {'id':<26} {'name':>5} {'type':>5} {'status':>7} {'mat-F1':>7}")
    for s in agg.per_record:
        print(
            f"  {s.id:<26} "
            f"{'✓' if s.name_correct else '✗':>5} "
            f"{'✓' if s.site_type_correct else '✗':>5} "
            f"{'✓' if s.status_correct else '✗':>7} "
            f"{s.materials.f1:>7.2f}"
        )

    print("\n  Overall metrics:")
    print(f"    Name accuracy        {agg.name_accuracy:.1%}")
    print(f"    Site-type accuracy   {agg.site_type_accuracy:.1%}")
    print(f"    Status accuracy      {agg.status_accuracy:.1%}")
    print(f"    Materials F1         {agg.materials_f1:.2f}")
    print(f"    Abstention rate      {agg.abstention_rate:.1%}")
    print(f"    Grounding rate       {agg.grounding_rate:.1%}")
    print("=" * 64 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the extractor against ground truth.")
    parser.add_argument("--mock", action="store_true", help="Offline self-test (no API key)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.mock)))


if __name__ == "__main__":
    main()
