# Senior AI Engineer Technical Test


> **Materials Extraction** : discover and enrich quarry records from messy public web sources.

---

## Contents

- [The problem](#the-problem)
- [A few words on the data](#a-few-words-on-the-data)
- [What to build](#what-to-build)
- [Output schema](#output-schema)
- [Example record](#example-record)
- [API surface](#api-surface)
- [Working notes](#working-notes)
- [What to send back](#what-to-send-back)

---

## The problem

ORIS keeps a global database of construction material sites. **This task is scoped to quarries only**; concrete plants, cement works, and asphalt plants are out of scope. The following image is an example of a quarry site.

![Quarry Example](assets/quarry.jpg)

The problem we'd like to solve is as follows :

> *For a given coordinate and radius, what quarries exist there, and are they still operating?*

Build the pipeline that answers that.

| | Description |
| :-- | :-- |
| **Input**  | a coordinate + radius (only) |
| **Output** | a structured, grounded record per quarry|

---

## A few words on the data

The web sources you'll touch are uneven:

- Public registries are inconsistent across countries.
- Operator websites are often a 2012 WordPress install with one PDF and no contact page.
- Directory aggregators repeat each other and quietly invent details.
- *"Last updated 2014"* might mean the site is still running, or that the quarry was filled in for housing.
- Some pages return `200` and serve nothing useful.

A good pipeline takes this as the territory, not the exception. **Confident extraction from a stale source is worse than no extraction.** If the system can't tell, the system should say so.

---

## What to build

A service that takes a coordinate + radius and returns enriched records for quarries discovered in that area.

The shape is open. You choose the discovery strategy, the scraping approach, the model, the orchestration, the storage. We care about what the system does and how it behaves.

That said, the following need to be true:

1. Everything should be packed into docker-compose
2. A `README.md` how to run it via docker compose up command
3. A simple UI app to run the task, watch its progress, view and evaluate results (no authentication is required)
4. A backend service to process the task. Backend should be following the standard crawling practices
5. Evaluation test case
6. Regression test suite

---

## Output schema

Every extraction validates against this. Partial fields are fine. **Invalid structure is not.**

<details>
<summary><strong>JSON Schema</strong></summary>

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["site_id", "schema_version", "input", "extraction", "provenance", "metrics", "run_metadata"],
  "properties": {
    "site_id":        { "type": "string", "description": "Stable hash of {latitude, longitude, radius_km, run_id}" },
    "schema_version": { "const": "2.0.0" },

    "input": {
      "type": "object",
      "required": ["latitude", "longitude", "radius_km"],
      "properties": {
        "latitude":  { "type": "number", "minimum": -90,  "maximum": 90 },
        "longitude": { "type": "number", "minimum": -180, "maximum": 180 },
        "radius_km": { "type": "number", "exclusiveMinimum": 0 }
      }
    },

    "extraction": {
      "type": "object",
      "properties": {
        "official_name":      { "$ref": "#/$defs/groundedString" },
        "site_type":          { "$ref": "#/$defs/groundedEnum" },
        "description":        { "$ref": "#/$defs/groundedString" },
        "materials_produced": { "type": "array", "items": { "$ref": "#/$defs/groundedString" } },
        "certifications":     { "type": "array", "items": { "$ref": "#/$defs/groundedString" } },
        "operational_status": { "$ref": "#/$defs/groundedEnum" },
        "location_verification": {
          "type": "object",
          "required": ["is_verified", "confidence", "method"],
          "properties": {
            "is_verified":    { "type": "boolean" },
            "confidence":     { "type": "number", "minimum": 0, "maximum": 1 },
            "extracted_city": { "type": ["string", "null"] },
            "method":         { "enum": ["string_match", "geocode", "llm_inference", "none"] }
          }
        }
      }
    },

    "provenance": {
      "type": "object",
      "required": ["sources", "reconciliations"],
      "properties": {
        "sources": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["source_id", "url", "fetched_at", "content_hash"],
            "properties": {
              "source_id":    { "type": "string" },
              "url":          { "type": "string", "format": "uri" },
              "fetched_at":   { "type": "string", "format": "date-time" },
              "content_hash": { "type": "string" },
              "trust_tier":   { "enum": ["official", "directory", "news", "unknown"] }
            }
          }
        },
        "reconciliations": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["field", "candidates", "winner_source_id", "reason"],
            "properties": {
              "field": { "type": "string" },
              "candidates": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "value":     {},
                    "source_id": { "type": "string" },
                    "score":     { "type": "number" }
                  }
                }
              },
              "winner_source_id": { "type": "string" },
              "reason":           { "type": "string" }
            }
          }
        }
      }
    },

    "metrics": {
      "type": "object",
      "required": ["llm_tokens_in", "llm_tokens_out", "usd_cost", "latency_ms", "model_calls"],
      "properties": {
        "llm_tokens_in":  { "type": "integer" },
        "llm_tokens_out": { "type": "integer" },
        "usd_cost":       { "type": "number" },
        "latency_ms":     { "type": "integer" },
        "model_calls": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["model", "purpose", "tokens_in", "tokens_out", "usd_cost"],
            "properties": {
              "model":      { "type": "string" },
              "purpose":    { "type": "string" },
              "tokens_in":  { "type": "integer" },
              "tokens_out": { "type": "integer" },
              "usd_cost":   { "type": "number" }
            }
          }
        }
      }
    },

    "run_metadata": {
      "type": "object",
      "required": ["run_id", "prompt_hash", "scraper_version", "created_at"],
      "properties": {
        "run_id":          { "type": "string" },
        "prompt_hash":     { "type": "string" },
        "scraper_version": { "type": "string" },
        "created_at":      { "type": "string", "format": "date-time" }
      }
    }
  },

  "$defs": {
    "groundedString": {
      "type": "object",
      "required": ["value", "confidence", "evidence"],
      "properties": {
        "value":          { "type": ["string", "null"] },
        "confidence":     { "type": "number", "minimum": 0, "maximum": 1 },
        "abstain_reason": { "type": ["string", "null"] },
        "evidence": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["source_id", "char_start", "char_end", "quote"],
            "properties": {
              "source_id":  { "type": "string" },
              "char_start": { "type": "integer", "minimum": 0 },
              "char_end":   { "type": "integer", "minimum": 0 },
              "quote":      { "type": "string" }
            }
          }
        }
      }
    },
    "groundedEnum": {
      "allOf": [{ "$ref": "#/$defs/groundedString" }],
      "properties": {
        "value": { "enum": ["Quarry", null] }
      }
    }
  }
}
```

</details>

A couple of points worth being explicit about:

- **Grounding is per-field.** `value` and `evidence` are co-located. A separate top-level `sources: [{url, snippet}]` list isn't grounding.
- **Abstaining is first-class.** `value: null` with an `abstain_reason` is a valid, expected output.

---

## Example record

<details>
<summary><strong>Abbreviated example</strong></summary>

```json
{
  "site_id": "a1f3c8d27e4b9",
  "schema_version": "2.0.0",
  "input": { "latitude": 48.8566, "longitude": 2.3522, "radius_km": 50 },
  "extraction": {
    "official_name": {
      "value": "Carrière de Vignats",
      "confidence": 0.92,
      "evidence": [
        { "source_id": "src_2", "char_start": 142, "char_end": 161, "quote": "Carrière de Vignats" }
      ]
    },
    "site_type": {
      "value": "Quarry",
      "confidence": 0.88,
      "evidence": [
        { "source_id": "src_2", "char_start": 803, "char_end": 838, "quote": "exploitation de roches calcaires" }
      ]
    },
    "operational_status": {
      "value": null,
      "confidence": 0.0,
      "abstain_reason": "no_recent_evidence",
      "evidence": []
    }
  },
  "provenance": {
    "sources": [
      { "source_id": "src_1", "url": "https://example-quarry.fr/",     "fetched_at": "2025-04-12T08:14:33Z", "content_hash": "sha256:9f...", "trust_tier": "official"  },
      { "source_id": "src_2", "url": "https://directory.example/...",  "fetched_at": "2025-04-12T08:14:51Z", "content_hash": "sha256:c3...", "trust_tier": "directory" }
    ],
    "reconciliations": [
      {
        "field": "site_type",
        "candidates": [
          { "value": "Quarry", "source_id": "src_2", "score": 0.88 },
          { "value": "Other",  "source_id": "src_1", "score": 0.41 }
        ],
        "winner_source_id": "src_2",
        "reason": "directory entry explicitly states limestone quarry; operator site uses generic 'site industriel'"
      }
    ]
  },
  "metrics": {
    "llm_tokens_in": 4127,
    "llm_tokens_out": 312,
    "usd_cost": 0.018,
    "latency_ms": 7340,
    "model_calls": []
  },
  "run_metadata": {
    "run_id": "r_2025_04_12_a1f3",
    "prompt_hash": "sha256:1a2b...",
    "scraper_version": "0.4.1",
    "created_at": "2025-04-12T08:15:02Z"
  }
}
```

</details>

---

## API surface

Extend as needed. The core endpoints:

| Method | Path | Purpose |
| :----- | :--- | :------ |
| `POST` | `/api/jobs`                              | Submit `{ latitude, longitude, radius_km, max_usd_cost? }` → `{ job_id }` |
| `GET`  | `/api/jobs/:id`                          | Current state, progress, result or error |
| `GET`  | `/api/sites`                             | List with `q`, `status` filters and pagination |
| `GET`  | `/api/sites/:id`                         | Full record with provenance |
| `GET`  | `/api/health`                            | Queue depth, worker count, recent error rate |

---

## Working notes

- **Deployment.** Docker Compose is enough. No cloud deployment expected.
- **Secrets.** One API key in `.env`. No secrets in the repo.
- **Politeness.** Respect `robots.txt`. Set a real `User-Agent`. Respect `Retry-After`. Add jitter.
- **Safety.** Validate URLs before fetching them. Don't follow open redirects.

---

## What to send back

A repo, public, private with access, containing :

1. **`README.md`** with:
   - Description of your architecture and the trade-offs you made,
   - one diagram of components and data flow,
   - your eval strategy and metrics,
   - a short list of known limitations and what you'd do next.
2. **`Makefile`** (or equivalent) where the following work on a clean machine with Docker, and appropriate structure for the UI and an API key in `.env`, example :
   ```sh
   make bootstrap
   make extract LAT="..." LON="..." RADIUS_KM="..."
   ```
3. **A small ground-truth set** and a script that scores against it, with an explanation of the result.
