# Pipeline

The extraction pipeline runs as a Celery background task, triggered when a job is submitted.

---

## Stage 1 — Discovery

**Module:** `backend/pipeline/discovery.py`

Queries the Overpass API (OpenStreetMap) for `landuse=quarry` and `man_made=quarry` features within the bounding box derived from the input coordinates and radius.

```
Overpass query → list of QuarryCandidate(name, lat, lon, osm_id)
                       │
                       ▼
              Web search per candidate
              → additional source URLs
```

**Fallback:** if Overpass returns 0 results, a web search is run for `"quarry" near [reverse-geocoded city]`.

---

## Stage 2 — Scraping

**Module:** `backend/pipeline/scraper.py`

For each URL collected during discovery:

1. Validate URL (http/https only, no private IPs).
2. Check `robots.txt` — skip if disallowed.
3. Fetch with `httpx` + polite delay (1s base + 0–1.5s jitter).
4. Hash content — skip if already in DB.
5. Clean HTML: remove nav/footer/scripts, extract main content, truncate to 8,000 tokens.

**Trust tier classification:**

| URL pattern | Tier |
|---|---|
| Operator's own domain | `official` |
| "annuaire", "directory", "brgm" | `directory` |
| News domains | `news` |
| Everything else | `unknown` |

---

## Stage 3 — LLM Extraction

**Module:** `backend/pipeline/extractor.py`

Sends cleaned page text to OpenAI gpt-4o with a structured prompt.

**Grounding contract** — every extracted value must come with:

```json
{
  "value": "Carrière de Vignats",
  "confidence": 0.92,
  "evidence": [
    { "source_id": "src_2", "char_start": 142, "char_end": 161, "quote": "Carrière de Vignats" }
  ]
}
```

**Abstention** — when evidence is absent or too old:

```json
{
  "value": null,
  "confidence": 0.0,
  "abstain_reason": "no_recent_evidence",
  "evidence": []
}
```

**Prompt caching:** the system prompt (~800 tokens) is cached with `cache_control: ephemeral`, reducing cost by ~90% on repeated calls.

---

## Stage 4 — Reconciliation

**Module:** `backend/pipeline/reconciler.py`

Merges extraction results from multiple sources for the same quarry.

For each field:
- Collect all candidate values with their source trust tier and confidence.
- Score = `trust_tier_score × confidence`.
- Pick the highest-scoring candidate as the winner.
- Log all candidates + winner reason in `provenance.reconciliations`.

| Trust tier | Score |
|---|---|
| `official` | 1.0 |
| `directory` | 0.6 |
| `news` | 0.5 |
| `unknown` | 0.3 |

---

## Stage 5 — Validation & Metrics

**Module:** `backend/pipeline/validator.py`

- Validates the final record against JSON Schema v2.0.0 — hard failure if invalid.
- Computes `site_id = sha256("{lat}:{lon}:{radius_km}:{run_id}")[:13]`.
- Aggregates `metrics`: total `tokens_in`, `tokens_out`, `usd_cost`, `latency_ms`.
