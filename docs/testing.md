# Testing

---

## Run tests

```sh
make test          # full suite (unit + integration)
make test-unit     # unit tests only
make eval          # evaluation against ground truth
```

---

## Unit tests (`tests/unit/`)

| File | What is tested |
|---|---|
| `test_discovery.py` | Overpass query builder, bounding box, fallback logic |
| `test_scraper.py` | URL validation, robots.txt enforcement, HTML cleaning |
| `test_extractor.py` | Prompt builder, response parser (mocked OpenAI API) |
| `test_reconciler.py` | Candidate scoring, winner selection, tie-breaking |
| `test_validator.py` | Schema validation pass/fail, site_id hash stability |
| `test_api.py` | All REST endpoints (mocked DB and queue) |

---

## Integration tests (`tests/integration/`)

- `test_pipeline.py` — full pipeline run against a known quarry (Overpass live, OpenAI mocked).
- `test_api_db.py` — API + real PostgreSQL via Docker testcontainers.

---

## Evaluation (`tests/eval/`)

### Ground truth format

```json
[
  {
    "input": { "latitude": 48.9, "longitude": 2.1, "radius_km": 20 },
    "expected": {
      "official_name": "Carrière de Vignats",
      "operational_status": "active",
      "materials_produced": ["calcaire"]
    }
  }
]
```

### Scoring script

```sh
uv run -- python tests/eval/score.py
# or
make eval
```

### Metrics computed per field

| Metric | Description |
|---|---|
| **Precision** | Extracted value matches expected (exact or fuzzy match) |
| **Abstention rate** | How often the system abstains vs. hallucinating |
| **Coverage** | Percentage of expected fields that are non-null |
| **Grounding rate** | Percentage of non-null fields with at least one evidence quote |

### Example output

```
Field                  Precision   Coverage   Grounding
─────────────────────────────────────────────────────
official_name          0.91        0.95       1.00
operational_status     0.72        0.60       0.98
materials_produced     0.83        0.88       1.00
─────────────────────────────────────────────────────
Overall                0.82        0.81       0.99
```
