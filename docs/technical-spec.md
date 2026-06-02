# Technical Specification

This page is a rendered version of the full technical specification.

---

## System Architecture

```
User (Browser)
     │
     ▼
┌─────────────┐     POST /api/jobs      ┌──────────────────┐
│  Frontend   │ ──────────────────────► │  FastAPI Backend  │
│  (React)    │ ◄────────────────────── │                  │
└─────────────┘     job_id              └────────┬─────────┘
                                                 │ enqueue
                                                 ▼
                                        ┌────────────────┐
                                        │  Redis (Queue) │
                                        └───────┬────────┘
                                                │ pick up
                                                ▼
                                        ┌────────────────┐
                                        │ Celery Worker  │
                                        └───────┬────────┘
                         ┌─────────────────────┼─────────────────────┐
                         ▼                     ▼                     ▼
                  ┌────────────┐     ┌──────────────────┐   ┌────────────────┐
                  │ Discovery  │     │ Scraper (httpx)  │   │ LLM (OpenAI)  │
                  │ (Overpass) │     │                  │   │               │
                  └────────────┘     └──────────────────┘   └────────────────┘
                                                 │ store
                                                 ▼
                                        ┌────────────────┐
                                        │  PostgreSQL    │
                                        └────────────────┘
```

---

## Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Backend | Python 3.12 + FastAPI | Async-native, Pydantic integration |
| Task Queue | Celery 5 + Redis 7 | Battle-tested async workers |
| Database | PostgreSQL 16 | JSONB for flexible record storage |
| HTTP Client | httpx (async) | Async, HTTP/2, timeout control |
| HTML Parsing | BeautifulSoup4 + lxml | Industry standard |
| LLM | OpenAI gpt-4o | Low hallucination, structured output |
| Geo Discovery | Overpass API (OSM) | Free, globally comprehensive |
| Web Search | DuckDuckGo Search | No API key, good coverage |
| Schema Validation | jsonschema 4 | JSON Schema Draft-07 |
| Frontend | React 18 + Vite | Lightweight, fast dev loop |
| Containerisation | Docker Compose v2 | Single-command deployment |

---

## Pipeline Stages

```
[coordinates + radius]
        │
        ▼
   DISCOVERY      ← Overpass API + web search
        │
        ▼
   SCRAPING       ← httpx + BeautifulSoup, robots.txt respected
        │
        ▼
   EXTRACTION     ← OpenAI API, grounded fields, explicit abstention
        │
        ▼
  RECONCILIATION  ← multi-source merge, winner selection
        │
        ▼
   VALIDATION     ← JSON Schema v2.0.0
        │
        ▼
   PostgreSQL
```

See [`TECHNICAL_SPEC.md`](../TECHNICAL_SPEC.md) for full details on each stage.
