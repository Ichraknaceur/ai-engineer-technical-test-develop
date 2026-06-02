"""Quarry domain entities: the raw candidate and the final enriched record."""

from dataclasses import dataclass, field


@dataclass
class QuarryCandidate:
    """A quarry site identified during the discovery stage, before enrichment.

    Produced by the IDiscoverer port (e.g. Overpass API) and fed into
    the scraping and extraction stages.

    Attributes:
        name:        Display name from the discovery source, if available.
        latitude:    Latitude of the site centre.
        longitude:   Longitude of the site centre.
        osm_id:      OpenStreetMap node/way/relation ID, if discovered via Overpass.
        source_urls: URLs collected for this candidate (operator site, directories, etc.).
    """

    name: str | None
    latitude: float
    longitude: float
    osm_id: str | None = None
    source_urls: list[str] = field(default_factory=list)


@dataclass
class QuarryRecord:
    """A fully enriched and validated quarry record conforming to output schema v2.0.0.

    This is the final artefact produced by the pipeline. Every field in
    `extraction` is grounded with evidence quotes from `provenance.sources`.

    Attributes:
        site_id:        Stable 13-char hash of {lat}:{lon}:{radius_km}:{run_id}.
        schema_version: Always "2.0.0".
        input:          The original search coordinates and radius.
        extraction:     Grounded field values (name, status, materials, etc.).
        provenance:     Source documents and reconciliation log.
        metrics:        LLM token counts, USD cost, and latency.
        run_metadata:   Run ID, prompt hash, scraper version, and creation timestamp.
    """

    site_id: str
    schema_version: str
    input: dict
    extraction: dict
    provenance: dict
    metrics: dict
    run_metadata: dict
