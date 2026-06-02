# Technical Specification — Quarry Extraction Pipeline

**Version:** 1.0.0
**Date:** 2026-06-02
**Author:** AI Engineer Technical Test

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [System Overview](#2-system-overview)
3. [Technology Stack](#3-technology-stack)
4. [Architecture](#4-architecture)
5. [Component Details](#5-component-details)
   - 5.1 [Discovery Module](#51-discovery-module)
   - 5.2 [Scraper Module](#52-scraper-module)
   - 5.3 [Extraction Module (LLM)](#53-extraction-module-llm)
   - 5.4 [Reconciliation & Validation](#54-reconciliation--validation)
   - 5.5 [Job Queue](#55-job-queue)
6. [API Reference](#6-api-reference)
7. [Database Schema](#7-database-schema)
8. [Output Schema](#8-output-schema)
9. [LLM Integration](#9-llm-integration)
10. [Scraping Rules & Politeness](#10-scraping-rules--politeness)
11. [Frontend](#11-frontend)
12. [Testing Strategy](#12-testing-strategy)
13. [Docker Compose Services](#13-docker-compose-services)
14. [Environment Variables](#14-environment-variables)
15. [Security Considerations](#15-security-considerations)
16. [Known Limitations](#16-known-limitations)

---

## 1. Problem Statement

Given a geographic coordinate (latitude, longitude) and a search radius in kilometers, the system must:

1. **Discover** all quarry sites within that area from public web sources.
2. **Enrich** each discovered site with structured metadata (name, materials, operational status, certifications, etc.).
3. **Ground** every extracted value with a traceable evidence quote from a source document.
4. **Abstain** explicitly when evidence is insufficient or stale rather than guessing.
5. **Return** a validated, schema-compliant JSON record per quarry.

> **Core principle:** A confident extraction from a stale source is worse than no extraction. The system must know when not to answer.

---

## 2. System Overview

```
User (Browser)
     │
     ▼
┌─────────────┐     POST /api/jobs      ┌──────────────────┐
│  Frontend   │ ──────────────────────► │   FastAPI Backend │
│  (React)    │ ◄────────────────────── │                  │
└─────────────┘     job_id              └────────┬─────────┘
                                                 │
                                         enqueue task
                                                 │
                                                 ▼
                                        ┌────────────────┐
                                        │  Redis (Queue) │
                                        └───────┬────────┘
                                                │
                                        pick up task
                                                │
                                                ▼
                                        ┌────────────────┐
                                        │ Celery Worker  │
                                        │  (Pipeline)    │
                                        └───────┬────────┘
                                                │
                        ┌───────────────────────┼───────────────────────┐
                        │                       │                       │
                        ▼                       ▼                       ▼
               ┌──────────────┐      ┌─────────────────┐    ┌──────────────────┐
               │  Discovery   │      │  Scraper Module │    │  LLM Extraction  │
               │  (Overpass + │      │  (httpx + BS4)  │    │  (Claude API)    │
               │  Web Search) │      │                 │    │                  │
               └──────────────┘      └─────────────────┘    └──────────────────┘
                        │                       │                       │
                        └───────────────────────┴───────────────────────┘
                                                │
                                        validate & store
                                                │
                                                ▼
                                        ┌────────────────┐
                                        │  PostgreSQL DB │
                                        └────────────────┘
```

---

## 3. Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Backend** | Python 3.12 + FastAPI | Async-native, fast, excellent Pydantic integration |
| **Task Queue** | Celery 5 + Redis 7 | Battle-tested async worker, Redis as broker and result backend |
| **Database** | PostgreSQL 16 | JSONB support for flexible schema storage, reliable, relational |
| **ORM / Migrations** | SQLAlchemy 2 + Alembic | Async ORM, type-safe, migration tooling |
| **HTTP Client** | httpx (async) | Async, supports HTTP/2, easy timeout and retry config |
| **HTML Parsing** | BeautifulSoup4 + lxml | Industry standard, battle-tested |
| **LLM** | OpenAI gpt-4o | Best-in-class instruction following, structured output, low hallucination |
| **Geo Discovery** | Overpass API (OpenStreetMap) | Free, globally comprehensive, reliable, coordinate-native |
| **Web Search** | DuckDuckGo Search (ddg-search) | No API key needed, good coverage, scraping-friendly |
| **Schema Validation** | jsonschema 4 | Standard JSON Schema Draft-07 validation |
| **Frontend** | React 18 + Vite | Lightweight, fast dev loop, no complex state needed |
| **Containerisation** | Docker Compose v2 | Single-command local deployment as required |
| **Testing** | pytest + pytest-asyncio + httpx | Async-compatible test suite |

---

## 4. Architecture

### 4.1 Request Lifecycle

```
1. User submits { latitude, longitude, radius_km } via UI
2. POST /api/jobs → backend creates Job record (status: pending) → returns job_id
3. Backend enqueues Celery task with job_id
4. UI polls GET /api/jobs/:id every 2s, displays progress
5. Celery worker picks up task:
   a. Discovery  → finds quarry candidates in the area
   b. For each candidate:
      i.  Web search  → finds relevant URLs (official site, directories, news)
      ii. Fetch       → downloads page content (respecting robots.txt)
      iii.Clean       → strips HTML, keeps readable text
      iv. Extract LLM → Claude extracts grounded fields from text
   c. Reconciliation → merges multi-source results, resolves conflicts
   d. Validation     → validates against JSON Schema v2.0.0
   e. Metrics        → computes tokens, cost, latency
   f. Persist        → stores Site record in PostgreSQL
6. Job status → completed
7. UI displays results list; user can click any site for full record + provenance
```

### 4.2 Pipeline Stages

```
[coordinates + radius]
        │
        ▼
┌──────────────────┐
│    DISCOVERY     │  Overpass API → quarry nodes/ways/relations in bbox
│                  │  Web search   → "quarry <city> site:*.fr" etc.
└────────┬─────────┘
         │  list of candidate quarries (name, coords, source URLs)
         ▼
┌──────────────────┐
│    SCRAPING      │  For each URL:
│                  │  - Check robots.txt
│                  │  - Fetch with polite delays + jitter
│                  │  - Hash content (dedup)
│                  │  - Clean HTML → plain text
└────────┬─────────┘
         │  list of (source_id, url, text, fetched_at, content_hash)
         ▼
┌──────────────────┐
│    EXTRACTION    │  Claude API:
│   (LLM)          │  - Structured prompt with text + schema
│                  │  - Returns grounded fields (value + evidence)
│                  │  - Abstains when unsure
└────────┬─────────┘
         │  list of per-source extraction results
         ▼
┌──────────────────┐
│ RECONCILIATION   │  Merge fields from multiple sources:
│                  │  - Score each candidate by source trust tier
│                  │  - Pick winner, record reason
│                  │  - Log all candidates in provenance.reconciliations
└────────┬─────────┘
         │  merged Site record
         ▼
┌──────────────────┐
│   VALIDATION     │  JSON Schema Draft-07 validation
│   + METRICS      │  Compute: tokens_in/out, usd_cost, latency_ms
└────────┬─────────┘
         │  validated record
         ▼
     PostgreSQL
```

---

## 5. Component Details

### 5.1 Discovery Module

**File:** `backend/pipeline/discovery.py`

**Responsibilities:**
- Query Overpass API for `landuse=quarry` and `man_made=quarry` nodes/ways/relations within the bounding box derived from `(lat, lon, radius_km)`.
- Run a web search query per discovered quarry name to find additional source URLs.
- Return a `List[QuarryCandidate]` with `name`, `osm_id`, `lat`, `lon`, `source_urls`.

**Overpass query pattern:**
```
[out:json][timeout:30];
(
  node["landuse"="quarry"](around:{radius_m},{lat},{lon});
  way["landuse"="quarry"](around:{radius_m},{lat},{lon});
  relation["landuse"="quarry"](around:{radius_m},{lat},{lon});
);
out center;
```

**Fallback:** If Overpass returns 0 results, fall back to a web search for `"quarry" OR "carrière" near [reverse-geocoded city name]`.

**Output type:**
```python
@dataclass
class QuarryCandidate:
    name: str | None
    osm_id: str | None
    latitude: float
    longitude: float
    source_urls: list[str]
```

---

### 5.2 Scraper Module

**File:** `backend/pipeline/scraper.py`

**Responsibilities:**
- Validate URLs (must be http/https, no private IP ranges, no open redirects).
- Check `robots.txt` before fetching; skip disallowed URLs.
- Fetch page content with `httpx.AsyncClient`.
- Apply polite delays: `base_delay=1.0s` + random jitter `[0, 1.5]s`.
- Return `ScrapedPage` with raw HTML, cleaned text, content hash, fetch timestamp.

**HTTP configuration:**
```python
headers = {
    "User-Agent": "QuarryBot/1.0 (research project; contact@example.com)"
}
timeout = httpx.Timeout(15.0)
max_redirects = 3
```

**Content cleaning pipeline:**
1. Parse HTML with BeautifulSoup (`lxml` parser).
2. Remove `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>` tags.
3. Extract main content: prioritise `<main>`, `<article>`, `<section>`.
4. Normalise whitespace; truncate to 8,000 tokens to stay within LLM context limits.

**Output type:**
```python
@dataclass
class ScrapedPage:
    source_id: str        # sha256 of URL
    url: str
    fetched_at: datetime
    content_hash: str     # sha256 of raw HTML
    cleaned_text: str
    trust_tier: Literal["official", "directory", "news", "unknown"]
    error: str | None
```

**Trust tier classification:**
| Pattern | Tier |
|---|---|
| URL matches OSM operator tag domain | `official` |
| URL contains "annuaire", "directory", "register", "brgm" | `directory` |
| URL is a news domain | `news` |
| Everything else | `unknown` |

---

### 5.3 Extraction Module (LLM)

**File:** `backend/pipeline/extractor.py`

**Responsibilities:**
- Send cleaned page text to Claude API with a structured prompt.
- Receive a JSON response conforming to the extraction fields.
- Each field must include `value`, `confidence`, `evidence` (list of `{source_id, char_start, char_end, quote}`).
- If evidence is absent or too old, set `value: null` and `abstain_reason`.

**Model:** `claude-sonnet-4-6`

**Prompt strategy:**
- System prompt: defines the grounding contract, abstention rules, output schema.
- User prompt: provides the cleaned text and the source_id.
- Output format: JSON (via `tool_use` / structured output).

**Prompt caching:** Apply `cache_control: {"type": "ephemeral"}` to the system prompt block to reduce cost on repeated calls within a session.

**Abstention rules enforced in prompt:**
- If the only evidence is older than 3 years and contradicts newer sources → abstain on `operational_status`.
- If a field cannot be located in the text at all → `value: null`, `abstain_reason: "not_found_in_source"`.
- If the text is in a language the model cannot reliably parse → `abstain_reason: "language_not_supported"`.

**Token budget per call:** ~6,000 tokens in / ~800 tokens out (estimated).

**Cost estimate:** ~$0.003–$0.015 per quarry (3–5 source pages × 1 Claude call each).

---

### 5.4 Reconciliation & Validation

**File:** `backend/pipeline/reconciler.py`

**Responsibilities:**
- Collect all per-source extraction results for a quarry.
- For each field, compare candidates across sources.
- Select the winner by: `trust_tier` score × `confidence` score.
- Record all candidates and the winner reason in `provenance.reconciliations`.
- Compute `site_id` as `sha256({latitude}:{longitude}:{radius_km}:{run_id})[:13]`.

**Trust tier scores:**
| Tier | Score |
|---|---|
| `official` | 1.0 |
| `directory` | 0.6 |
| `news` | 0.5 |
| `unknown` | 0.3 |

**File:** `backend/pipeline/validator.py`

- Load JSON Schema `v2.0.0` from `backend/schemas/site_schema.json`.
- Validate final record with `jsonschema.validate()`.
- Raise `ValidationError` with field path if invalid — this is a hard failure.

---

### 5.5 Job Queue

**File:** `backend/worker/tasks.py`

**Celery configuration:**
```python
broker_url = "redis://redis:6379/0"
result_backend = "redis://redis:6379/1"
task_serializer = "json"
task_acks_late = True          # only ack after task completes
worker_prefetch_multiplier = 1 # one task at a time per worker
task_soft_time_limit = 300     # 5 min soft limit
task_time_limit = 360          # 6 min hard limit
```

**Job status transitions:**
```
pending → running → completed
                 ↘ failed
```

**Progress reporting:** Worker updates `Job.progress` (0–100) and `Job.status_message` in PostgreSQL at each pipeline stage. Frontend polls this.

---

## 6. API Reference

All endpoints return JSON. Errors follow `{ "detail": "..." }` (FastAPI default).

### `POST /api/jobs`

Submit a new extraction job.

**Request body:**
```json
{
  "latitude": 48.8566,
  "longitude": 2.3522,
  "radius_km": 50,
  "max_usd_cost": 1.0
}
```

**Response `202 Accepted`:**
```json
{
  "job_id": "j_abc123",
  "status": "pending",
  "created_at": "2026-06-02T10:00:00Z"
}
```

---

### `GET /api/jobs/:id`

Poll job status and retrieve results when complete.

**Response `200`:**
```json
{
  "job_id": "j_abc123",
  "status": "running",
  "progress": 45,
  "status_message": "Scraping 3/7 sources",
  "sites_found": 2,
  "created_at": "2026-06-02T10:00:00Z",
  "completed_at": null,
  "error": null
}
```

---

### `GET /api/sites`

List all extracted sites with optional filters.

**Query params:** `q` (text search), `status` (operational_status), `page`, `page_size`

**Response `200`:**
```json
{
  "total": 12,
  "page": 1,
  "results": [
    {
      "site_id": "a1f3c8d27e4b9",
      "official_name": "Carrière de Vignats",
      "operational_status": null,
      "latitude": 48.9,
      "longitude": 2.1,
      "created_at": "2026-06-02T10:05:00Z"
    }
  ]
}
```

---

### `GET /api/sites/:id`

Full record with provenance.

**Response `200`:** Full JSON matching the output schema (see §8).

---

### `GET /api/health`

System health check.

**Response `200`:**
```json
{
  "status": "ok",
  "queue_depth": 3,
  "worker_count": 1,
  "recent_error_rate": 0.02,
  "db": "ok",
  "redis": "ok"
}
```

---

## 7. Database Schema

### Table: `jobs`

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(32)` PK | `j_` + uuid4 |
| `latitude` | `FLOAT` | |
| `longitude` | `FLOAT` | |
| `radius_km` | `FLOAT` | |
| `max_usd_cost` | `FLOAT` | nullable |
| `status` | `VARCHAR(16)` | `pending / running / completed / failed` |
| `progress` | `INT` | 0–100 |
| `status_message` | `TEXT` | human-readable progress label |
| `sites_found` | `INT` | count of sites in this job |
| `error` | `TEXT` | nullable, populated on failure |
| `created_at` | `TIMESTAMPTZ` | |
| `completed_at` | `TIMESTAMPTZ` | nullable |

### Table: `sites`

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(32)` PK | `site_id` hash |
| `job_id` | `VARCHAR(32)` FK → jobs | |
| `schema_version` | `VARCHAR(8)` | `"2.0.0"` |
| `latitude` | `FLOAT` | from input |
| `longitude` | `FLOAT` | from input |
| `radius_km` | `FLOAT` | from input |
| `official_name` | `VARCHAR(512)` | nullable, denormalised for search |
| `operational_status` | `VARCHAR(64)` | nullable, denormalised for filter |
| `record` | `JSONB` | full validated output record |
| `created_at` | `TIMESTAMPTZ` | |

> The full validated record is stored as JSONB in `sites.record`. Denormalised columns (`official_name`, `operational_status`) exist solely to support fast API filtering without unpacking JSON.

---

## 8. Output Schema

Schema version: `2.0.0` (see `backend/schemas/site_schema.json`).

Key design principles:

**Grounded fields** — every extracted value is co-located with its evidence:
```json
{
  "value": "Carrière de Vignats",
  "confidence": 0.92,
  "evidence": [
    { "source_id": "src_2", "char_start": 142, "char_end": 161, "quote": "Carrière de Vignats" }
  ]
}
```

**Explicit abstention** — `null` with a reason is a valid, expected output:
```json
{
  "value": null,
  "confidence": 0.0,
  "abstain_reason": "no_recent_evidence",
  "evidence": []
}
```

**`site_id`** — stable hash of `{latitude}:{longitude}:{radius_km}:{run_id}`, truncated to 13 chars.

**`schema_version`** — const `"2.0.0"`, validates that consumer code and producer are in sync.

---

## 9. LLM Integration

### Model

`claude-sonnet-4-6` — chosen for its strong instruction following, low hallucination rate on structured extraction tasks, and cost-effective pricing at scale.

### Prompt Architecture

```
[System prompt — cached]
You are a structured data extraction assistant specialized in industrial site records.
Your task: extract quarry metadata from the provided web page text.

Rules:
- Every non-null value MUST be grounded by an exact quote from the text.
- char_start/char_end refer to character offsets in the provided text.
- If you cannot find reliable evidence for a field, set value=null and provide abstain_reason.
- Do not infer or guess. Extract only what is explicitly stated.
- If the page is clearly about a different site or unrelated topic, set all fields to null.
- operational_status: only assert "active" if there is evidence from the last 3 years.

Output format: JSON matching the extraction schema below.
[schema definition]

[User prompt — per page]
source_id: {source_id}
trust_tier: {trust_tier}
fetched_at: {fetched_at}

--- PAGE TEXT START ---
{cleaned_text}
--- PAGE TEXT END ---
```

### Prompt Caching

The system prompt (≈ 800 tokens) is marked with `cache_control: {"type": "ephemeral"}`. This reduces cost by ~90% on the prompt tokens when the same worker processes multiple pages in the same session.

### Cost Control

- `max_usd_cost` parameter on the job caps total spend.
- Worker checks cumulative cost before each LLM call and stops if the limit would be exceeded.
- Remaining sites are marked with `abstain_reason: "budget_exceeded"`.

---

## 10. Scraping Rules & Politeness

| Rule | Implementation |
|---|---|
| Respect `robots.txt` | `urllib.robotparser.RobotFileParser` checked before every fetch |
| Real `User-Agent` | `QuarryBot/1.0 (research; contact@example.com)` |
| Rate limiting | 1.0s base delay between requests to the same domain |
| Jitter | `random.uniform(0, 1.5)` added to base delay |
| `Retry-After` | Parsed from 429 response headers; worker sleeps accordingly |
| Timeout | 15s connect + read timeout per request |
| Max redirects | 3 (open redirect protection) |
| URL validation | Must be `http`/`https`; reject private IPs (RFC 1918); no `file://`, `ftp://` |
| Content dedup | Skip fetch if `content_hash` already exists in DB |
| Max pages/quarry | 5 source pages maximum per quarry candidate |

---

## 11. Frontend

**Tech:** React 18 + Vite + plain CSS (no UI framework dependency).

### Pages / Views

| View | Description |
|---|---|
| **Home** | Form: latitude, longitude, radius_km, optional max_usd_cost. Submit button. |
| **Job Progress** | Progress bar (polls `/api/jobs/:id` every 2s). Stage label. Cancel button. |
| **Results List** | Table of found quarries: name, status, confidence, coordinates. Pagination. Filter by status. |
| **Site Detail** | Full record view: extraction fields with confidence badges, evidence quotes highlighted, provenance sources list, reconciliation log, metrics (cost, latency, tokens). |

### UI Design Principles

- No authentication required.
- Mobile-friendly layout.
- Confidence scores displayed as colour-coded badges: green (≥ 0.8), yellow (0.5–0.8), red (< 0.5).
- `null` values displayed as `— (abstained: {reason})`.
- Evidence quotes shown inline under each field on the detail page.

---

## 12. Testing Strategy

### Unit Tests (`tests/unit/`)

| Module | What is tested |
|---|---|
| `test_discovery.py` | Overpass query builder, bounding box calculation, fallback logic |
| `test_scraper.py` | URL validation, robots.txt enforcement, HTML cleaning, trust tier classification |
| `test_extractor.py` | Prompt builder, response parser, grounding validation (mocked Claude API) |
| `test_reconciler.py` | Candidate scoring, winner selection, tie-breaking |
| `test_validator.py` | Schema validation pass/fail cases, site_id hash stability |
| `test_api.py` | All API endpoints (mocked DB and queue) |

### Integration Tests (`tests/integration/`)

- `test_pipeline.py` — full pipeline run against a known quarry (Overpass live, Claude mocked).
- `test_api_db.py` — API + real PostgreSQL (via Docker testcontainers).

### Evaluation (`tests/eval/`)

**Ground truth file:** `tests/eval/ground_truth.json`

Structure:
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

**Scoring script:** `tests/eval/score.py`

Metrics computed per field:
- **Precision** — extracted value matches expected value (exact or fuzzy string match).
- **Abstention rate** — how often the system abstains when it should (vs. hallucinating).
- **Coverage** — percentage of expected fields that are non-null in the output.
- **Grounding rate** — percentage of non-null fields that have at least one evidence quote.

Output: tabular report per field + overall score (0–1).

### Regression Tests

`make test` runs all unit + integration tests. CI-equivalent: `pytest --cov=backend --cov-report=term-missing`.

---

## 13. Docker Compose Services

| Service | Image | Port | Notes |
|---|---|---|---|
| `backend` | `./backend` (Dockerfile) | `8000` | FastAPI app |
| `worker` | `./backend` (same image) | — | Celery worker, command override |
| `frontend` | `./frontend` (Dockerfile) | `3000` | Vite dev or nginx prod |
| `postgres` | `postgres:16-alpine` | `5432` | Volume: `pgdata` |
| `redis` | `redis:7-alpine` | `6379` | No persistence needed |

**Startup order:** `postgres` and `redis` must be healthy before `backend` and `worker` start. Implemented via `depends_on: { condition: service_healthy }`.

**Health checks:**
- `postgres`: `pg_isready`
- `redis`: `redis-cli ping`
- `backend`: `GET /api/health`

---

## 14. Environment Variables

All secrets live in `.env` (never committed). `.env.example` is committed.

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://user:pass@postgres:5432/quarry` |
| `REDIS_URL` | Yes | `redis://redis:6379/0` |
| `SCRAPER_USER_AGENT` | No | Override default User-Agent string |
| `MAX_PAGES_PER_QUARRY` | No | Default: `5` |
| `BASE_SCRAPE_DELAY_S` | No | Default: `1.0` |
| `LOG_LEVEL` | No | Default: `INFO` |

---

## 15. Security Considerations

| Risk | Mitigation |
|---|---|
| SSRF via user-supplied URLs | Only Overpass/search-derived URLs are fetched; validate scheme (`http/https` only); block RFC 1918 + loopback IPs |
| Open redirect | Max 3 redirects; validate each redirect target against same URL rules |
| Prompt injection via page content | Page text is inserted in a clearly delimited block (`--- PAGE TEXT START ---`); system prompt establishes strict extraction-only contract |
| API key leakage | Key loaded from env var; never logged; `.env` in `.gitignore` |
| Denial of service via large pages | Content truncated to 8,000 tokens before LLM call; HTTP response size capped at 5 MB |
| SQL injection | SQLAlchemy ORM with parameterised queries throughout |

---

## 16. Known Limitations

| Limitation | Impact | Potential fix |
|---|---|---|
| No JavaScript rendering | Sites with JS-only content return empty text | Add optional Playwright fallback for detected SPAs |
| Overpass data lag | OSM edits can take hours to index | Cross-reference with government open data registries (e.g. BRGM for France) |
| Language coverage | Prompt tuned for French/English | Add language detection + per-language prompt templates |
| Operational status staleness | No real-time business registry access | Integrate national business registries (SIRENE, Companies House) |
| Cost unpredictability | Variable page count per quarry | Implement per-job cost estimation before running; enforce hard cap |
| No deduplication across jobs | Same quarry may appear in multiple jobs | Add canonical site merging by OSM ID or coordinate proximity |
| Rate limiting on Overpass | Busy instances throttle heavy queries | Implement exponential backoff; cache Overpass results by bbox |
