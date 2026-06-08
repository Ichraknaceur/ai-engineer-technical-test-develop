# Quarry Extraction Pipeline

> **Materials Extraction**: discover and enrich quarry records from messy public web sources.

---

## What it does

Given a geographic coordinate and a radius, the pipeline:

1. **Discovers** quarry sites in the area via OpenStreetMap (Overpass API) and web search.
2. **Scrapes** relevant web pages (operator sites, directories, press) following politeness rules.
3. **Extracts** structured metadata using OpenAI (name, materials, operational status, certifications).
4. **Grounds** every value with an exact text quote and character offsets from the source.
5. **Abstains** explicitly when evidence is insufficient or stale.
6. **Returns** a validated, schema-compliant JSON record per quarry found.

---

## Quick start

```sh
# First-time setup
make bootstrap

# Run an extraction
make extract LAT=48.8566 LON=2.3522 RADIUS_KM=50

# Preview these docs locally
make docs-serve

# Deploy docs to GitHub Pages
make docs-deploy
```

---

## Core design principle

!!! warning "Confident extraction from a stale source is worse than no extraction."
    If the system cannot find reliable recent evidence for a field, it sets `value: null`
    with an `abstain_reason` rather than guessing. Abstaining is a first-class, valid output.

---

## Navigation

| Section | Description |
|---|---|
| [Technical Spec](technical-spec.md) | Full architecture, stack choices, data flow |
| [API Reference](api.md) | All REST endpoints with request/response examples |
| [Pipeline](pipeline.md) | Discovery → Scraping → Extraction → Reconciliation |
| [Testing](testing.md) | Unit tests, evaluation, scoring strategy |
| [Deployment](deployment.md) | Docker Compose setup, environment variables |
