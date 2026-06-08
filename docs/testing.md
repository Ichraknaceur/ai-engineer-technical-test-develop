# Testing

```sh
make test               # full suite (unit + integration) with coverage
make test-unit          # unit tests only (no Docker needed)
make test-integration   # integration tests (spins up a PostgreSQL container)
make eval               # score the extractor against ground truth (needs OPENAI_API_KEY)
make eval-mock          # offline self-test of the eval harness (no key, no cost)
```

External services (Overpass, DuckDuckGo, OpenAI) are always mocked in tests —
no network calls, no LLM cost.

---

## Unit tests (`tests/unit/`)

Domain logic and adapters with mocked I/O. Highlights:

| Area | What is tested |
|---|---|
| `infrastructure/overpass_discoverer_test.py` | Bounding box, element parsing, multi-instance fallback |
| `infrastructure/web_search_enricher_test.py` | Relevance filter (rejects job boards/dictionaries), query building |
| `infrastructure/http_scraper_test.py` | URL/SSRF validation, robots.txt, HTML cleaning, `429` handling, trust tier |
| `infrastructure/llm_extractor_test.py` | Provider-agnostic extraction, abstention, error/invalid-JSON handling |
| `application/pipeline_steps_test.py` | Discovery/Reconciler/Validator steps, trust-tier scoring |
| `infrastructure/jobs_router_test.py`, `sites_router_test.py` | REST endpoints (mocked services) |
| `eval/scorer_test.py` | Scoring maths: fuzzy match, set F1, abstention/grounding |

Test files follow the `*_test.py` convention (enforced by pre-commit).

---

## Integration tests (`tests/integration/`)

Run against a **real PostgreSQL** started on the fly via `testcontainers`
(`conftest.py`); skipped automatically if Docker is unavailable.

| File | What is tested |
|---|---|
| `job_repository_test.py` | Job save/get/update/list round-trip |
| `site_repository_test.py` | JSONB persistence, `q`/`status` filters, pagination |
| `api_end_to_end_test.py` | FastAPI + real DB (create/get/list/404/422), queue mocked |

These cover the repository and ORM-mapping code that mocks cannot exercise.

---

## Evaluation (`tests/eval/`)

The eval scores the LLM extractor against a hand-verified ground-truth set. Each
entry carries a **fixed cleaned-text excerpt** so the score is reproducible
regardless of live web variance.

**Ground-truth format** (`tests/eval/ground_truth.json`):

```json
{
  "entries": [
    {
      "id": "granulats_vicat",
      "source_id": "src_eval_1",
      "source_text": "Granulats Vicat. ... nous produisons ... granulats ... sable et gravier ...",
      "expected": {
        "official_name": "Granulats Vicat",
        "site_type": "Quarry",
        "operational_status": "active",
        "materials_produced": ["sand", "gravel"]
      }
    }
  ]
}
```

The set includes **negative cases** — a closed quarry (expects `inactive`) and an
irrelevant job-board page (must abstain on every field) — to test that the system
knows when *not* to answer.

**Metrics**

| Metric | Definition |
|---|---|
| Name / type / status accuracy | Fuzzy (name) or exact (type/status) match; a correct abstention counts as correct |
| Materials F1 | Set-based precision/recall with FR/EN synonym collapsing |
| Abstention rate | Share of fields returned as `null` rather than guessed |
| Grounding rate | Share of non-null fields backed by ≥1 evidence quote |

**Results (gpt-4o, live)**

```
Name accuracy        100.0%
Site-type accuracy   100.0%
Status accuracy      100.0%
Materials F1         0.79
Abstention rate      20.0%
Grounding rate       100.0%
```

The scoring logic itself is covered by 17 unit tests, so a regression in the
metric maths is caught without spending tokens.
