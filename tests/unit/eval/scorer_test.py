"""Unit tests for the evaluation scoring logic (tests/eval/scorer.py)."""

from tests.eval.scorer import (
    aggregate,
    exact_matches,
    name_matches,
    score_record,
    score_set,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _grounded(value, with_evidence=True):
    if value is None:
        return {"value": None, "confidence": 0.0, "evidence": [], "abstain_reason": "no_evidence"}
    return {
        "value": value,
        "confidence": 0.9,
        "evidence": [{"source_id": "s", "char_start": 0, "char_end": 1, "quote": "x"}]
        if with_evidence
        else [],
    }


def _entry(**expected):
    return {"id": "e1", "expected": expected}


# ---------------------------------------------------------------------------
# name_matches / exact_matches
# ---------------------------------------------------------------------------


class TestStringMatching:
    def test_name_containment_both_directions(self):
        assert name_matches("Granulats Vicat", "Vicat") is True
        assert name_matches("Vicat", "Granulats Vicat") is True

    def test_name_case_insensitive(self):
        assert name_matches("CARRIÈRE", "carrière") is True

    def test_name_no_match(self):
        assert name_matches("Alpha", "Beta") is False

    def test_name_none_is_false(self):
        assert name_matches(None, "Vicat") is False
        assert name_matches("Vicat", None) is False

    def test_exact_match(self):
        assert exact_matches("Quarry", "quarry") is True
        assert exact_matches("active", "inactive") is False


# ---------------------------------------------------------------------------
# score_set (materials P/R/F1 with synonyms)
# ---------------------------------------------------------------------------


class TestScoreSet:
    def test_perfect_match(self):
        score = score_set(["sand", "gravel"], ["sand", "gravel"])
        assert score.f1 == 1.0

    def test_synonyms_collapse(self):
        # "granulats" → aggregate, "sable" → sand
        score = score_set(["granulats", "sable"], ["aggregate", "sand"])
        assert score.f1 == 1.0

    def test_partial_overlap(self):
        score = score_set(["sand", "clay"], ["sand", "gravel"])
        assert score.precision == 0.5
        assert score.recall == 0.5
        assert score.f1 == 0.5

    def test_both_empty_is_perfect(self):
        score = score_set([], [])
        assert score.f1 == 1.0

    def test_predicted_empty_expected_present(self):
        score = score_set([], ["sand"])
        assert score.recall == 0.0
        assert score.f1 == 0.0


# ---------------------------------------------------------------------------
# score_record
# ---------------------------------------------------------------------------


class TestScoreRecord:
    def test_all_correct(self):
        entry = _entry(
            official_name="Granulats Vicat",
            site_type="Quarry",
            operational_status="active",
            materials_produced=["sand", "gravel"],
        )
        extraction = {
            "official_name": _grounded("Granulats Vicat"),
            "site_type": _grounded("Quarry"),
            "operational_status": _grounded("active"),
            "description": _grounded("desc"),
            "materials_produced": [_grounded("sand"), _grounded("gravel")],
        }
        score = score_record(entry, extraction)
        assert score.name_correct
        assert score.site_type_correct
        assert score.status_correct
        assert score.materials.f1 == 1.0
        assert score.abstained_fields == 0

    def test_abstention_counted(self):
        entry = _entry(
            official_name=None, site_type=None, operational_status=None, materials_produced=[]
        )
        extraction = {
            "official_name": _grounded(None),
            "site_type": _grounded(None),
            "operational_status": _grounded(None),
            "description": _grounded(None),
            "materials_produced": [],
        }
        score = score_record(entry, extraction)
        assert score.abstained_fields == 4
        assert score.non_null_fields == 0

    def test_correct_abstention_on_name_counts_as_correct(self):
        entry = _entry(
            official_name=None, site_type=None, operational_status=None, materials_produced=[]
        )
        extraction = {
            "official_name": _grounded(None),
            "site_type": _grounded(None),
            "operational_status": _grounded(None),
            "description": _grounded(None),
            "materials_produced": [],
        }
        score = score_record(entry, extraction)
        assert score.name_correct is True
        assert score.site_type_correct is True
        assert score.status_correct is True

    def test_hallucinated_name_when_abstention_expected_is_wrong(self):
        entry = _entry(
            official_name=None, site_type=None, operational_status=None, materials_produced=[]
        )
        extraction = {
            "official_name": _grounded("Invented Name"),
            "site_type": _grounded(None),
            "operational_status": _grounded(None),
            "description": _grounded(None),
            "materials_produced": [],
        }
        score = score_record(entry, extraction)
        assert score.name_correct is False

    def test_grounding_counted_only_with_evidence(self):
        entry = _entry(
            official_name="X",
            site_type="Quarry",
            operational_status="active",
            materials_produced=[],
        )
        extraction = {
            "official_name": _grounded("X", with_evidence=True),
            "site_type": _grounded("Quarry", with_evidence=False),
            "operational_status": _grounded("active", with_evidence=True),
            "description": _grounded(None),
            "materials_produced": [],
        }
        score = score_record(entry, extraction)
        assert score.non_null_fields == 3
        assert score.grounded_fields == 2  # site_type has no evidence


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------


class TestAggregate:
    def test_empty_returns_zeros(self):
        agg = aggregate([])
        assert agg.count == 0

    def test_averages_across_records(self):
        entry_ok = _entry(
            official_name="Vicat",
            site_type="Quarry",
            operational_status="active",
            materials_produced=["sand"],
        )
        entry_bad = _entry(
            official_name="Alpha",
            site_type="Quarry",
            operational_status="active",
            materials_produced=["sand"],
        )
        good = score_record(
            entry_ok,
            {
                "official_name": _grounded("Vicat"),
                "site_type": _grounded("Quarry"),
                "operational_status": _grounded("active"),
                "description": _grounded(None),
                "materials_produced": [_grounded("sand")],
            },
        )
        bad = score_record(
            entry_bad,
            {
                "official_name": _grounded("Wrong"),
                "site_type": _grounded("Quarry"),
                "operational_status": _grounded("active"),
                "description": _grounded(None),
                "materials_produced": [_grounded("sand")],
            },
        )
        agg = aggregate([good, bad])
        assert agg.count == 2
        assert agg.name_accuracy == 0.5
        assert agg.site_type_accuracy == 1.0
