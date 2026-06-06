# Quarry Extraction Pipeline

> For a given coordinate and radius, what quarries exist there, and are they still operating?

[![CI](https://github.com/ichraknaceurr/ai-engineer-technical-test-develop/actions/workflows/ci.yml/badge.svg)](https://github.com/ichraknaceurr/ai-engineer-technical-test-develop/actions/workflows/ci.yml)
[![Deploy Docs](https://github.com/ichraknaceurr/ai-engineer-technical-test-develop/actions/workflows/docs.yml/badge.svg)](https://github.com/ichraknaceurr/ai-engineer-technical-test-develop/actions/workflows/docs.yml)

---

## Quick Start

```sh
# 1. Clone the repository
git clone https://github.com/ichraknaceurr/ai-engineer-technical-test-develop.git
cd ai-engineer-technical-test-develop

# 2. Configure environment
cp .env.example .env
# edit .env → set OPENAI_API_KEY=sk-...

# 3. Build Docker images
make bootstrap

# 4. Start all services (postgres, redis, backend, worker)
make up
# → API + Swagger UI: http://localhost:8000/docs

# 5. Run an extraction from the CLI
make extract LAT=48.8566 LON=2.3522 RADIUS_KM=50
```

> DB migrations run automatically on backend startup via the Docker entrypoint.

---

## Architecture

### Components & Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser                                                        │
│  React UI  ──── POST /api/jobs ────────────────────────────►   │
│            ◄─── job_id ─────────────────────────────────────   │
│            ──── GET  /api/jobs/:id (poll every 2s) ─────────►  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   FastAPI Backend   │
                    │   (Python 3.12)     │
                    └──────────┬──────────┘
                               │ enqueue
                    ┌──────────▼──────────┐
                    │   Redis (queue)     │
                    └──────────┬──────────┘
                               │ pick up
                    ┌──────────▼──────────┐
                    │   Celery Worker     │
                    └──┬────────┬─────────┘
                       │        │
          ┌────────────▼─┐  ┌───▼────────────┐
          │  Discovery   │  │    Scraper     │
          │  Overpass    │  │  httpx + BS4   │
          │  API (OSM)   │  │  robots.txt    │
          └────────────┬─┘  └───┬────────────┘
                       │        │
                    ┌──▼────────▼──────────┐
                    │   LLM Extraction     │
                    │   OpenAI gpt-4o      │
                    │   grounding +        │
                    │   abstention         │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Reconciliation    │
                    │   + Validation      │
                    │   JSON Schema v2    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │    PostgreSQL       │
                    └─────────────────────┘
```

### Hexagonal Architecture (Ports & Adapters)

```
backend/
├── domain/          # Pure business logic — zero external dependencies
├── ports/           # Python Protocols (interfaces) — inbound + outbound
├── application/     # Use cases — orchestrate domain through ports
└── infrastructure/  # Adapters — FastAPI, PostgreSQL, Redis, OpenAI, httpx
```

The domain never imports from infrastructure. Every external dependency is
injected through a port interface, making the system fully testable without
real databases, queues, or API keys.

---

## Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Backend | Python 3.12 + FastAPI | Async-native, Pydantic validation |
| Task Queue | Celery 5 + Redis 7 | Battle-tested async workers |
| Database | PostgreSQL 16 + JSONB | Flexible schema storage |
| HTTP Client | httpx (async) | Polite crawling with timeout control |
| HTML Parsing | BeautifulSoup4 + lxml | Robust content extraction |
| LLM | OpenAI gpt-4o (swappable) | Provider-agnostic — swap to Claude/Mistral via `ILLMProvider` |
| Geo Discovery | Overpass API (OSM) | Free, globally comprehensive, coordinate-native |
| Web Search | DuckDuckGo Search | No API key needed, good coverage |
| Frontend | React 18 + Vite | Lightweight, fast dev loop |
| Containerisation | Docker Compose v2 | Single-command local deployment |
| Code Quality | ruff + ty + pre-commit | Fast linting, type checking, git hooks |
| CI/CD | GitHub Actions | Automated quality checks + docs deploy |

---

## Architecture Decisions & Trade-offs

### Hexagonal architecture over a flat service layer
**Why:** Allows swapping any adapter (e.g. replace OpenAI with another LLM, or PostgreSQL with SQLite for tests) without touching business logic. The cost is more boilerplate up front.

### Overpass API (OpenStreetMap) as primary discovery
**Why:** Free, no rate-limit key needed, globally comprehensive for `landuse=quarry`. Trade-off: OSM data can lag real-world changes by hours to days. The `OVERPASS_URL` env var lets you point to a private instance to avoid public rate limits.

### DuckDuckGo for web search enrichment
**Why:** No API key, no quota, scraping-friendly. Used to find operator sites and registry pages for each candidate. Trade-off: results are non-deterministic and can vary between runs.

### Provider-agnostic LLM extractor
**Why:** `LLMExtractor` takes any object satisfying `ILLMProvider` (OpenAI, Claude, Mistral). Swapping the model is one line — `LLMExtractor(provider=ClaudeProvider())` — without touching extraction logic, prompts, or tests. Current default: OpenAI gpt-4o.

### urllib over httpx for Overpass requests
**Why:** Several public Overpass instances reject httpx's default headers (connection keep-alive, accept-encoding) while accepting standard urllib requests. Wrapped in `asyncio.to_thread` to stay non-blocking.

### Explicit abstention over best-guess extraction
**Why:** A confident wrong answer is worse than no answer. The system sets `value: null` with an `abstain_reason` when evidence is insufficient or stale. This reduces recall but eliminates hallucinated data.

### Per-field grounding (value + evidence co-located)
**Why:** Forces the LLM to cite its sources inline. A top-level `sources` list is not grounding — it doesn't tell you which source justified which value.

### JSONB storage for the full record
**Why:** The output schema evolves; JSONB avoids migrations for schema changes. Denormalised columns (`official_name`, `operational_status`) exist only for fast API filtering.

### Celery + Redis over asyncio background tasks
**Why:** Celery survives worker restarts and supports retries, time limits, and multiple workers. The trade-off is operational overhead (Redis service + worker process).

---

## Evaluation Strategy

### Ground truth
A small set of known quarries in `tests/eval/ground_truth.json`, manually verified against public registries.

### Metrics per field

| Metric | Description |
|---|---|
| **Precision** | Extracted value matches the expected value (exact or fuzzy) |
| **Abstention rate** | How often the system abstains vs. hallucinating when evidence is absent |
| **Coverage** | Percentage of expected fields that are non-null |
| **Grounding rate** | Percentage of non-null fields backed by at least one evidence quote |

### Run the evaluation

```sh
make eval
```

---

## Known Limitations

| Limitation | Impact | What I'd do next |
|---|---|---|
| No JavaScript rendering | Sites with JS-only content return empty text | Add optional Playwright fallback |
| OSM data lag | Quarries added/closed recently may be missed | Cross-reference BRGM (France) or national open data |
| Overpass public rate limits | 406/429 after repeated requests from same IP | Set `OVERPASS_URL` to a private instance |
| DuckDuckGo non-determinism | Search results vary between runs | Cache results per candidate + run_id |
| Operational status staleness | No real-time business registry access | Integrate SIRENE / Companies House APIs |
| Search relevance is FR/EN only | Quarry-signal keywords + search queries cover French and English; sites in DE/ES/IT may be filtered out | Add per-language keyword sets + localised search queries driven by the country of the coordinates |
| LLM prompt tuned for FR/EN | Extraction prompt examples are French/English | Language detection + per-language prompt templates |
| Weak evidence alignment | LLM may cite a nearby span instead of the exact value (e.g. materials grounded on the site name) | Validate that each field's quote actually contains the extracted value; abstain otherwise |
| No cross-job deduplication | Same quarry can appear in multiple jobs | Merge by OSM ID or coordinate proximity |
| Cost unpredictability | Variable page count per quarry | Pre-estimate cost before running; show user a quote |

---

## Debug Endpoints

Available at `http://localhost:8000/docs` once the stack is running.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Check postgres, redis, worker connectivity |
| `GET /api/discovery?lat=&lon=&radius_km=&enrich=&limit=` | Overpass discovery, optionally enriched with web search URLs |
| `GET /api/scrape?url=` | Fetch and clean a single URL through the polite scraper |
| `GET /api/extract?url=` | Scrape + LLM extraction on a single URL (uses OpenAI credits) |

```sh
# Discover quarries around Lyon (raw Overpass candidates)
curl "http://localhost:8000/api/discovery?lat=45.7640&lon=4.8357&radius_km=30"

# Discover + enrich the first 5 candidates with web search source URLs
curl "http://localhost:8000/api/discovery?lat=45.764&lon=4.835&radius_km=30&enrich=true&limit=5"

# Scrape a page (verify content before spending LLM tokens)
curl "http://localhost:8000/api/scrape?url=https://www.vicat.fr/nos-solutions/nos-expertises/granulats"

# Full scrape + extraction
curl "http://localhost:8000/api/extract?url=https://www.vicat.fr/nos-solutions/nos-expertises/granulats"
```

### Discovery + web search example

`GET /api/discovery?lat=45.764&lon=4.835&radius_km=30&enrich=true&limit=5`

```json
{
  "total": 78,
  "enriched": 1,
  "candidates": [
    { "name": "Anciennes Carrières des Torrelles", "osm_id": "node/1531294920", "source_urls": [] },
    {
      "name": "Eco Ressources",
      "osm_id": "node/10069563951",
      "source_urls": [
        "https://www.georisques.gouv.fr/webappReport/ws/installations/document/7390YAf...",
        "https://www.georisques.gouv.fr/webappReport/ws/installations/inspection/q24ZNKG..."
      ]
    },
    { "name": "Carrière de Mions", "osm_id": "way/38965815", "source_urls": [] }
  ]
}
```

The relevance filter keeps only sources carrying an **unambiguous** quarry signal
(`granulats`, `calcaire`, `quarry`, a registry domain like `georisques.gouv.fr`...).
The French word *carrière* alone (quarry **or** career) is deliberately rejected,
which previously let job boards, dictionaries, and retirement sites through.
The trade-off is lower recall: a real quarry with no findable authoritative source
yields `source_urls: []` and the pipeline abstains rather than attaching junk —
consistent with the brief's "say so when you can't tell" principle.

### Real extraction example

`GET /api/extract?url=https://www.vicat.fr/nos-solutions/nos-expertises/granulats`

```json
{
  "url": "https://www.vicat.fr/nos-solutions/nos-expertises/granulats",
  "trust_tier": "official",
  "word_count": 1888,
  "scrape_error": null,
  "extraction": {
    "official_name": {
      "value": "Granulats Vicat",
      "confidence": 0.9,
      "evidence": [{ "source_id": "src_5e098b81", "char_start": 0, "char_end": 15, "quote": "Granulats Vicat" }]
    },
    "site_type": {
      "value": "Quarry",
      "confidence": 0.9,
      "evidence": [{ "source_id": "src_5e098b81", "char_start": 0, "char_end": 15, "quote": "Granulats Vicat" }]
    },
    "description": {
      "value": "Matière première naturelle indispensable pour la fabrication de béton, nous produisons plusieurs millions de tonnes de granulats par an.",
      "confidence": 0.9,
      "evidence": [{ "source_id": "src_5e098b81", "char_start": 108, "char_end": 197, "quote": "...nous produisons plusieurs millions de tonnes de granulats par an." }]
    },
    "operational_status": {
      "value": "active",
      "confidence": 0.9,
      "evidence": [{ "source_id": "src_5e098b81", "char_start": 108, "char_end": 197, "quote": "...nous produisons plusieurs millions de tonnes de granulats par an." }]
    },
    "materials_produced": [
      { "value": "sand",   "confidence": 0.9, "evidence": [...] },
      { "value": "gravel", "confidence": 0.9, "evidence": [...] }
    ],
    "certifications": [],
    "location_verification": { "is_verified": false, "confidence": 0, "extracted_city": null, "method": "none" }
  },
  "metrics": { "model": "gpt-4o", "tokens_in": 3396, "tokens_out": 578, "usd_cost": 0.0257, "latency_ms": 5253 }
}
```

> **Grounding note:** `materials_produced` (sand/gravel) is correctly extracted but
> its evidence points to the site name rather than the exact material mention — the
> model inferred the materials and cited a nearby span. Tightening evidence↔quote
> alignment (reject a field when its quote does not contain the value) is tracked as
> future work in [Known Limitations](#known-limitations).

### Full job example — multi-source reconciliation

A complete job (`POST /api/jobs` → worker → `GET /api/sites/:id`) around Lyon
produced this persisted record. Note that `materials_produced` merges values from
**two different sources**: the operator site (`src_f724904b`) and a registry page
(`src_ea0e494b`).

```json
{
  "site_id": "5da202eaa5dd4",
  "schema_version": "2.0.0",
  "input": { "latitude": 45.764, "longitude": 4.835, "radius_km": 30 },
  "extraction": {
    "official_name": {
      "value": "GROUPE Gachet",
      "confidence": 0.9,
      "evidence": [{ "source_id": "src_f724904b", "char_start": 9, "char_end": 22, "quote": "GROUPE Gachet" }]
    },
    "description": {
      "value": "Leader spécialisé dans les granulats et béton, le GROUPE Gachet évolue depuis 1931...",
      "confidence": 0.9,
      "evidence": [{ "source_id": "src_f724904b", "char_start": 23, "char_end": 276, "quote": "Leader spécialisé dans les granulats et béton..." }]
    },
    "certifications": [
      { "value": "NF", "confidence": 0.9, "evidence": [{ "source_id": "src_f724904b", "char_start": 515, "char_end": 517, "quote": "NF" }] }
    ],
    "materials_produced": [
      { "value": "granulats", "confidence": 0.9, "evidence": [{ "source_id": "src_f724904b", "char_start": 23, "char_end": 32, "quote": "granulats" }] },
      { "value": "béton",     "confidence": 0.9, "evidence": [{ "source_id": "src_f724904b", "char_start": 37, "char_end": 42, "quote": "béton" }] },
      { "value": "sand",      "confidence": 0.9, "evidence": [{ "source_id": "src_ea0e494b", "char_start": 276, "char_end": 336, "quote": "Exploitation de gravières et sablières, extraction d'argiles et de kaolin" }] },
      { "value": "clay",      "confidence": 0.9, "evidence": [{ "source_id": "src_ea0e494b", "char_start": 276, "char_end": 336, "quote": "Exploitation de gravières et sablières, extraction d'argiles et de kaolin" }] }
    ]
  }
}
```

After filtering, this job persisted **5 clean records** (operators with authoritative
sources) instead of flooding the database with empty abstentions for all 78 raw OSM
candidates.

---

## Development

```sh
make bootstrap     # First-time setup: copy .env, build Docker images
make up            # Start all services (http://localhost:8000)
make down          # Stop all containers
make test          # Full test suite with coverage
make lint          # Ruff linting
make typecheck     # ty type checking (domain + ports + application)
make precommit     # Run all pre-commit hooks
make docs-serve    # Preview docs at http://localhost:8090
```

---

## Project Structure

```
.
├── backend/
│   ├── domain/          # Entities, value objects, exceptions
│   ├── ports/           # Inbound + outbound Protocol interfaces
│   ├── application/     # Services + pipeline steps
│   └── infrastructure/  # FastAPI, PostgreSQL, Celery, OpenAI, httpx
├── frontend/            # React 18 + Vite
├── tests/
│   ├── unit/            # Domain + application tests (mocked adapters)
│   ├── integration/     # API + real PostgreSQL
│   └── eval/            # Ground truth + scoring script
├── docs/                # MkDocs documentation
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

<details>
<summary>Original test brief</summary>

The original problem statement can be found in the
[ORIS Materials Extraction brief](TECHNICAL_SPEC.md).

</details>
