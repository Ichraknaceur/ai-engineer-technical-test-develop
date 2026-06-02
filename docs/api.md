# API Reference

Base URL: `http://localhost:8000`

All endpoints return JSON. Errors follow `{ "detail": "..." }`.

---

## POST `/api/jobs`

Submit a new extraction job.

**Request body**

```json
{
  "latitude": 48.8566,
  "longitude": 2.3522,
  "radius_km": 50,
  "max_usd_cost": 1.0
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `latitude` | float | Yes | −90 to 90 |
| `longitude` | float | Yes | −180 to 180 |
| `radius_km` | float | Yes | > 0 |
| `max_usd_cost` | float | No | Hard cap on LLM spend |

**Response `202`**

```json
{
  "job_id": "j_abc123",
  "status": "pending",
  "created_at": "2026-06-02T10:00:00Z"
}
```

---

## GET `/api/jobs/:id`

Poll job status and retrieve results when complete.

**Response `200`**

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

| Status | Meaning |
|---|---|
| `pending` | Queued, not started |
| `running` | Worker is processing |
| `completed` | Done, sites available |
| `failed` | Error — see `error` field |

---

## GET `/api/sites`

List extracted sites with optional filters and pagination.

**Query parameters**

| Param | Type | Description |
|---|---|---|
| `q` | string | Text search on site name |
| `status` | string | Filter by `operational_status` |
| `page` | int | Default: 1 |
| `page_size` | int | Default: 20, max: 100 |

**Response `200`**

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

## GET `/api/sites/:id`

Full record with provenance, evidence, and metrics.

**Response `200`** — full JSON matching output schema v2.0.0.

---

## GET `/api/health`

System health check.

**Response `200`**

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
