# API Reference

Base URL: `http://localhost:8000`. Interactive Swagger UI at
`http://localhost:8000/docs`.

All endpoints return JSON. Validation errors return `422` with FastAPI's
`{ "detail": [...] }` shape; not-found returns `404` with `{ "detail": "..." }`.

---

## Core endpoints

### POST `/api/jobs`

Submit a new extraction job.

**Request body**

```json
{ "latitude": 48.8566, "longitude": 2.3522, "radius_km": 50, "max_usd_cost": 1.0 }
```

| Field | Type | Required | Description |
|---|---|---|---|
| `latitude` | float | Yes | −90 to 90 |
| `longitude` | float | Yes | −180 to 180 |
| `radius_km` | float | Yes | > 0, ≤ 500 |
| `max_usd_cost` | float | No | Hard cap on LLM spend |

**Response `201`** — the full job object:

```json
{
  "id": "j_abc123",
  "latitude": 48.8566,
  "longitude": 2.3522,
  "radius_km": 50.0,
  "status": "pending",
  "progress": 0,
  "status_message": "",
  "sites_found": 0,
  "max_usd_cost": 1.0,
  "error": null,
  "created_at": "2026-06-02T10:00:00Z",
  "completed_at": null
}
```

---

### GET `/api/jobs`

List recent jobs, newest first.

| Param | Type | Description |
|---|---|---|
| `limit` | int | Max jobs to return (1–100, default 50) |

Returns a JSON array of job objects (same shape as above).

---

### GET `/api/jobs/{job_id}`

Poll a single job's state. Returns the job object, or `404` if unknown.

| Status | Meaning |
|---|---|
| `pending` | Queued, not started |
| `running` | Worker is processing (`progress`, `status_message` update live) |
| `completed` | Done — sites available via `/api/sites` |
| `failed` | Error — see the `error` field |

---

### GET `/api/sites`

List extracted site records with optional filters and pagination.

| Param | Type | Description |
|---|---|---|
| `q` | string | Substring match on official name |
| `status` | string | Filter by `operational_status` (e.g. `active`) |
| `page` | int | 1-based (default 1) |
| `page_size` | int | Default 20, max 100 |

**Response `200`**

```json
{
  "total": 5,
  "page": 1,
  "page_size": 20,
  "items": [ { "site_id": "a1f3c8d27e4b9", "schema_version": "2.0.0", "extraction": { ... }, "provenance": { ... }, "metrics": { ... } } ]
}
```

Each item is the full record (schema v2.0.0), not a flattened summary.

---

### GET `/api/sites/{site_id}`

Full record with grounded extraction, provenance (sources + reconciliations),
and metrics. Returns `404` if unknown.

---

### GET `/api/health`

```json
{ "status": "ok", "database": "ok", "redis": "ok" }
```

`status` is `ok` when both dependencies are reachable, `degraded` otherwise.

---

## Debug endpoints

These run individual pipeline stages without a full job — handy for validating
behaviour and (for `/extract`) checking the prompt before spending tokens.

| Endpoint | Purpose |
|---|---|
| `GET /api/discovery?lat=&lon=&radius_km=&enrich=&limit=` | Overpass discovery, optionally enriched with web-search URLs |
| `GET /api/scrape?url=` | Fetch + clean a single URL through the polite scraper |
| `GET /api/extract?url=` | Scrape + LLM extraction on a single URL (uses OpenAI credits) |
| `GET /api/pipeline/test?lat=&lon=&radius_km=` | Discovery → Scrape → Extract → Reconcile on the first candidate, **without** persisting |
