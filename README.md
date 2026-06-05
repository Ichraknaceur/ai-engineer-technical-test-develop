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
| LLM | OpenAI gpt-4o | Strong instruction following, structured output |
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
| Language coverage | Prompt tuned for French / English | Language detection + per-language prompt templates |
| No cross-job deduplication | Same quarry can appear in multiple jobs | Merge by OSM ID or coordinate proximity |
| Cost unpredictability | Variable page count per quarry | Pre-estimate cost before running; show user a quote |

---

## Debug Endpoints

Available at `http://localhost:8000/docs` once the stack is running.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Check postgres, redis, worker connectivity |
| `GET /api/discovery?lat=&lon=&radius_km=` | Run Overpass discovery and return raw candidates |
| `GET /api/scrape?url=` | Fetch and clean a single URL through the polite scraper |

Examples:
```sh
# Discover quarries around Paris
curl "http://localhost:8000/api/discovery?lat=48.8566&lon=2.3522&radius_km=50"

# Scrape a page
curl "http://localhost:8000/api/scrape?url=https://infoterre.brgm.fr"
```

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
