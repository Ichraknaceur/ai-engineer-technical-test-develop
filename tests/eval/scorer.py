"""Pure scoring functions for evaluating quarry extractions against ground truth.

Kept free of I/O and LLM calls so the scoring logic can be unit-tested
deterministically. The CLI in ``score.py`` wires these to real extractions.
"""

from dataclasses import dataclass, field

# Material synonyms — collapse FR/EN variants to a canonical token so that
# "granulats", "aggregates", "sable", "sand" don't count as misses.
_MATERIAL_SYNONYMS = {
    "granulats": "aggregate",
    "granulat": "aggregate",
    "aggregates": "aggregate",
    "aggregate": "aggregate",
    "sable": "sand",
    "sand": "sand",
    "gravier": "gravel",
    "graviers": "gravel",
    "gravel": "gravel",
    "calcaire": "limestone",
    "limestone": "limestone",
    "granit": "granite",
    "granite": "granite",
    "argile": "clay",
    "argiles": "clay",
    "clay": "clay",
    "béton": "concrete",
    "beton": "concrete",
    "concrete": "concrete",
    "kaolin": "kaolin",
    "ballast": "ballast",
}


def _normalize(text: str | None) -> str:
    """Lowercase and strip a string for comparison; None becomes empty."""
    return (text or "").strip().lower()


def _canonical_material(value: str) -> str:
    """Map a raw material string to its canonical synonym token."""
    norm = _normalize(value)
    return _MATERIAL_SYNONYMS.get(norm, norm)


def name_matches(predicted: str | None, expected: str | None) -> bool:
    """Fuzzy name match: case-insensitive containment in either direction.

    Accepts "Granulats Vicat" vs "Vicat" or "Carrière de Mions" vs "mions".
    """
    p, e = _normalize(predicted), _normalize(expected)
    if not p or not e:
        return False
    return p in e or e in p


def exact_matches(predicted: str | None, expected: str | None) -> bool:
    """Case-insensitive exact match (used for site_type, operational_status)."""
    return _normalize(predicted) == _normalize(expected)


@dataclass
class SetScore:
    """Precision / recall / F1 for a set-valued field (e.g. materials)."""

    precision: float
    recall: float
    f1: float
    matched: int
    predicted_count: int
    expected_count: int


def score_set(predicted: list[str], expected: list[str]) -> SetScore:
    """Compute precision/recall/F1 between predicted and expected value sets.

    Values are canonicalised via the material synonym map before comparison.
    """
    pred = {_canonical_material(v) for v in predicted if v}
    exp = {_canonical_material(v) for v in expected if v}

    if not pred and not exp:
        return SetScore(1.0, 1.0, 1.0, 0, 0, 0)

    matched = len(pred & exp)
    precision = matched / len(pred) if pred else 0.0
    recall = matched / len(exp) if exp else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return SetScore(precision, recall, f1, matched, len(pred), len(exp))


def _grounded_value(field_obj) -> str | None:
    """Pull the value from a groundedString-shaped dict, or None."""
    if isinstance(field_obj, dict):
        return field_obj.get("value")
    return None


def _has_evidence(field_obj) -> bool:
    """True if a groundedString field carries at least one evidence quote."""
    return bool(isinstance(field_obj, dict) and field_obj.get("evidence"))


@dataclass
class RecordScore:
    """Scoring outcome for a single ground-truth entry."""

    id: str
    name_correct: bool
    site_type_correct: bool
    status_correct: bool
    materials: SetScore
    abstained_fields: int
    grounded_fields: int
    non_null_fields: int


def score_record(entry: dict, extraction: dict) -> RecordScore:
    """Score one extraction dict against one ground-truth entry.

    Args:
        entry:      A ground-truth entry with an ``expected`` block.
        extraction: The extraction dict produced for that entry.

    Returns:
        A RecordScore with per-field correctness and grounding stats.
    """
    expected = entry["expected"]

    pred_name = _grounded_value(extraction.get("official_name"))
    pred_type = _grounded_value(extraction.get("site_type"))
    pred_status = _grounded_value(extraction.get("operational_status"))
    pred_materials = [
        m.get("value") for m in extraction.get("materials_produced", []) if isinstance(m, dict)
    ]

    # A correct abstention (expected None, predicted None) counts as correct.
    exp_name = expected.get("official_name")
    name_correct = pred_name is None if exp_name is None else name_matches(pred_name, exp_name)

    scalar_fields = ["official_name", "site_type", "description", "operational_status"]
    abstained = sum(1 for f in scalar_fields if _grounded_value(extraction.get(f)) is None)
    non_null = sum(1 for f in scalar_fields if _grounded_value(extraction.get(f)) is not None)
    grounded = sum(
        1
        for f in scalar_fields
        if _grounded_value(extraction.get(f)) is not None and _has_evidence(extraction.get(f))
    )

    return RecordScore(
        id=entry["id"],
        name_correct=name_correct,
        site_type_correct=exact_matches(pred_type, expected.get("site_type")),
        status_correct=exact_matches(pred_status, expected.get("operational_status")),
        materials=score_set(pred_materials, expected.get("materials_produced", [])),
        abstained_fields=abstained,
        grounded_fields=grounded,
        non_null_fields=non_null,
    )


@dataclass
class Aggregate:
    """Aggregated metrics across all scored records."""

    count: int = 0
    name_accuracy: float = 0.0
    site_type_accuracy: float = 0.0
    status_accuracy: float = 0.0
    materials_f1: float = 0.0
    abstention_rate: float = 0.0
    grounding_rate: float = 0.0
    per_record: list[RecordScore] = field(default_factory=list)


def aggregate(scores: list[RecordScore]) -> Aggregate:
    """Average per-record scores into overall evaluation metrics."""
    if not scores:
        return Aggregate()

    n = len(scores)
    total_abstainable = sum(4 for _ in scores)  # 4 scalar fields per record
    total_abstained = sum(s.abstained_fields for s in scores)
    total_non_null = sum(s.non_null_fields for s in scores)
    total_grounded = sum(s.grounded_fields for s in scores)

    return Aggregate(
        count=n,
        name_accuracy=sum(s.name_correct for s in scores) / n,
        site_type_accuracy=sum(s.site_type_correct for s in scores) / n,
        status_accuracy=sum(s.status_correct for s in scores) / n,
        materials_f1=sum(s.materials.f1 for s in scores) / n,
        abstention_rate=total_abstained / total_abstainable if total_abstainable else 0.0,
        grounding_rate=total_grounded / total_non_null if total_non_null else 1.0,
        per_record=scores,
    )
