# Pipeline

The extraction pipeline runs as a Celery background task
(`backend/infrastructure/worker/tasks.py`), triggered when a job is submitted.
The orchestrator is `ExtractionPipeline.run()` in
`backend/application/pipeline/pipeline.py`.

```
Discovery → Web search → Scraping → LLM extraction → Reconciliation → Validation → Persist
```

---

## Stage 1 — Discovery

**Modules:** `backend/application/pipeline/discovery.py` (orchestration),
`backend/infrastructure/discovery/overpass.py` (Overpass adapter).

Queries the Overpass API (OpenStreetMap) for `landuse=quarry` nodes, ways, and
relations within the bounding box derived from the input coordinates and radius.
The bbox is clamped to valid lat/lon ranges, and the request falls back across
several public Overpass instances if the primary is unavailable.

```
Overpass query → list of QuarryCandidate(name, lat, lon, osm_id, source_urls)
```

The `OVERPASS_URL` env var lets you point to a private instance to avoid public
rate limits.

---

## Stage 2 — Web search enrichment

**Module:** `backend/infrastructure/discovery/web_search.py`

For each **named** candidate, runs DuckDuckGo searches and keeps only results
carrying a **positive quarry signal** — an unambiguous keyword
(`granulats`, `calcaire`, `quarry`, `limestone`…) in the title/snippet/URL, or a
known registry domain (`georisques.gouv.fr`, `societe.com`,
`annuaire-entreprises.data.gouv.fr`…).

The ambiguous bare word *carrière* (quarry **or** career in French) is
deliberately rejected, which filters out job boards, dictionaries, and
retirement sites. Unnamed candidates are skipped — they have no findable web
presence. This favours precision over recall: a real quarry with no findable
authoritative source yields no URLs and the pipeline abstains rather than
attaching junk.

---

## Stage 3 — Scraping

**Module:** `backend/infrastructure/scraper/http_scraper.py`

For each source URL collected during discovery:

1. **Validate** the URL — http/https only, and reject hosts that resolve to
   private/loopback/link-local IP ranges (SSRF guard).
2. Skip URLs known to be useless (search forms, dictionaries, career sites).
3. **Check `robots.txt`** — skip if disallowed.
4. **Fetch** with `httpx` after a polite delay (configurable base + ±50% jitter);
   respect `Retry-After` on `429`.
5. **Clean** the HTML with BeautifulSoup4 + lxml — strip scripts/styles/nav/
   footer, normalise whitespace, truncate to ~8,000 words.
6. **Hash** the raw HTML (`content_hash`, SHA-256) for traceability.

The scraper **never raises** — failures are returned as `ScrapedPage.error`, so
one bad page does not abort the job.

**Trust tier classification** (inferred from the domain):

| URL pattern | Tier |
|---|---|
| Operator's own domain | `official` |
| `annuaire`, `registre`, `brgm`, `georisques`, `societe.com`… | `directory` |
| News domains (`actu`, `presse`, `lemonde`…) | `news` |
| Everything else | `unknown` |

---

## Stage 4 — LLM Extraction

**Modules:** `backend/infrastructure/llm/llm_extractor.py` (provider-agnostic),
`backend/infrastructure/llm/providers/openai_provider.py` (OpenAI gpt-4o).

The extractor is decoupled from any specific provider via the `ILLMProvider`
protocol — swapping to Claude or Mistral is one line. The default provider calls
OpenAI gpt-4o in JSON mode at `temperature=0` for deterministic structured output.

**Grounding contract** — every non-null value carries evidence:

```json
{
  "value": "Granulats Vicat",
  "confidence": 0.9,
  "evidence": [
    { "source_id": "src_5e098b81", "char_start": 0, "char_end": 15, "quote": "Granulats Vicat" }
  ]
}
```

**Abstention** — when evidence is absent, vague, stale, or contradictory:

```json
{
  "value": null,
  "confidence": 0.0,
  "abstain_reason": "no_evidence",
  "evidence": []
}
```

Valid `abstain_reason` values: `no_evidence`, `insufficient_evidence`,
`stale_evidence`, `contradictory_evidence`. The extractor tracks
`tokens_in`/`tokens_out`/`usd_cost` per call for the metrics record, and returns
a fully-abstained result (without calling the API) for empty or errored pages.

---

## Stage 5 — Reconciliation

**Module:** `backend/application/pipeline/reconciler.py`

Merges per-source extractions for the same quarry.

- **Scalar fields** (name, type, status, description): collect all candidate
  values, score each as `trust_tier_score × confidence`, pick the highest.
- **Array fields** (materials, certifications): merge all unique values across
  sources (synonym-aware), so e.g. `granulats` from the operator site and `sand`
  from a registry both survive.
- All competing decisions are logged in `provenance.reconciliations`.

| Trust tier | Score |
|---|---|
| `official` | 1.0 |
| `directory` | 0.6 |
| `news` | 0.5 |
| `unknown` | 0.3 |

---

## Stage 6 — Validation & Persistence

**Modules:** `backend/application/pipeline/validator.py`,
`backend/infrastructure/db/repositories/site_repository.py`.

- Validate the assembled record against JSON Schema v2.0.0
  (`backend/schemas/site_schema.json`) — a hard failure means the record is
  **not** persisted.
- `site_id = sha256("{lat}:{lon}:{radius_km}:{job_id}")[:13]`.
- Aggregate `metrics`: `llm_tokens_in`, `llm_tokens_out`, `usd_cost`,
  `latency_ms`, and the per-call `model_calls` list.
- Persist the full record as JSONB; the job progress and `sites_found` are
  updated throughout, and a `max_usd_cost` budget cap stops the run early if hit.
