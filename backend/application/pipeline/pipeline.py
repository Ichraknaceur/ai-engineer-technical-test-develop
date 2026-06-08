"""Main pipeline orchestrator that runs all extraction stages for a given job."""

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from backend.application.pipeline.discovery import DiscoveryStep
from backend.application.pipeline.reconciler import ReconcilerStep
from backend.application.pipeline.validator import ValidatorStep
from backend.config import settings
from backend.domain.entities.job import Job, JobStatus
from backend.domain.entities.quarry import QuarryRecord
from backend.domain.exceptions import ValidationError
from backend.infrastructure.llm.llm_extractor import LLMExtractor
from backend.infrastructure.scraper.http_scraper import HttpScraper, is_useful_url
from backend.ports.outbound.job_repository import IJobRepository
from backend.ports.outbound.site_repository import ISiteRepository

logger = logging.getLogger(__name__)

_SCRAPER_VERSION = "1.0.0"


class ExtractionPipeline:
    """Orchestrates the full quarry extraction pipeline for a single job.

    Stages:
    1. Discovery  — find quarry candidates (Overpass + web search).
    2. Scraping   — fetch and clean source pages per candidate.
    3. Extraction — LLM extracts grounded fields from each page.
    4. Reconciliation — merge multi-source results, resolve conflicts.
    5. Validation — validate the final record against JSON Schema v2.0.0.
    6. Persistence — store the validated record, update job progress.

    Args:
        job_repo:  Adapter for reading/updating Job entities.
        site_repo: Adapter for persisting validated QuarryRecord entities.
    """

    def __init__(
        self,
        job_repo: IJobRepository,
        site_repo: ISiteRepository,
    ) -> None:
        self._job_repo = job_repo
        self._site_repo = site_repo

    async def run(self, job_id: str) -> None:
        """Execute all pipeline stages for the given job.

        Args:
            job_id: Unique identifier of the job to process.
        """
        job = await self._job_repo.get(job_id)
        if job is None:
            logger.error("Job %s not found — aborting pipeline", job_id)
            return

        try:
            await self._run_pipeline(job)
        except Exception as exc:
            logger.exception("Unhandled error in pipeline for job %s", job_id)
            await self._fail(job, str(exc))

    async def _run_pipeline(self, job: Job) -> None:
        """Internal pipeline execution with progress tracking."""
        run_id = f"r_{uuid.uuid4().hex[:12]}"

        # Mark job as running
        job.status = JobStatus.RUNNING
        job.status_message = "Starting discovery..."
        job.progress = 5
        await self._job_repo.update(job)

        # ── Stage 1: Discovery ────────────────────────────────────────────
        discovery = DiscoveryStep()
        candidates = await discovery.run(_coords_from_job(job))

        job.progress = 20
        job.status_message = f"Found {len(candidates)} candidate(s) — scraping sources..."
        await self._job_repo.update(job)

        if not candidates:
            await self._complete(job, sites_found=0)
            return

        # ── Stages 2–4: Scrape + Extract + Reconcile per candidate ───────
        scraper = HttpScraper()
        extractor = LLMExtractor()
        reconciler = ReconcilerStep()
        validator = ValidatorStep()

        total_candidates = len(candidates)
        sites_saved = 0
        total_cost = 0.0

        for idx, candidate in enumerate(candidates):
            progress = 20 + int(70 * idx / total_candidates)
            job.progress = progress
            job.status_message = (
                f"Processing candidate {idx + 1}/{total_candidates}: {candidate.name or 'unnamed'}"
            )
            await self._job_repo.update(job)

            # Budget guard
            if job.max_usd_cost and total_cost >= job.max_usd_cost:
                logger.info(
                    "Budget cap $%.2f reached after %d candidates — stopping", job.max_usd_cost, idx
                )
                break

            # Filter and scrape useful URLs
            useful_urls = [u for u in candidate.source_urls if is_useful_url(u)]
            useful_urls = useful_urls[: settings.max_pages_per_quarry]

            if not useful_urls:
                logger.debug("Candidate %r has no useful URLs — skipping", candidate.name)
                continue

            pages = []
            sources = []
            for url in useful_urls:
                page = await scraper.fetch(url)
                pages.append(page)
                sources.append(
                    {
                        "source_id": page.source_id,
                        "url": page.url,
                        "fetched_at": page.fetched_at.isoformat(),
                        "content_hash": page.content_hash,
                        "trust_tier": page.trust_tier,
                    }
                )

            # LLM extraction per page
            extractions = []
            model_calls = []
            for page in pages:
                extraction = await extractor.extract(page)
                metrics = extraction.pop("_metrics", {})
                total_cost += metrics.get("usd_cost", 0.0)
                if metrics.get("tokens_in", 0) > 0:
                    model_calls.append(metrics)
                extractions.append(extraction)

            # Reconciliation
            reconciled = reconciler.run(extractions, sources)

            # Build full record
            site_id = _site_id(candidate, job)
            record = {
                "site_id": site_id,
                "schema_version": "2.0.0",
                "input": {
                    "latitude": job.latitude,
                    "longitude": job.longitude,
                    "radius_km": job.radius_km,
                },
                "extraction": reconciled["extraction"],
                "provenance": {
                    "sources": sources,
                    "reconciliations": reconciled["reconciliations"],
                },
                "metrics": {
                    "llm_tokens_in": sum(m.get("tokens_in", 0) for m in model_calls),
                    "llm_tokens_out": sum(m.get("tokens_out", 0) for m in model_calls),
                    "usd_cost": round(total_cost, 6),
                    "latency_ms": sum(m.get("latency_ms", 0) for m in model_calls),
                    "model_calls": model_calls,
                },
                "run_metadata": {
                    "run_id": run_id,
                    "job_id": job.id,
                    "prompt_hash": model_calls[0].get("prompt_hash", "") if model_calls else "",
                    "scraper_version": _SCRAPER_VERSION,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            }

            # Validation
            try:
                validator.run(record)
            except ValidationError as exc:
                logger.warning(
                    "Record for %r failed validation — skipping: %s", candidate.name, exc
                )
                continue

            # Persist
            quarry_record = QuarryRecord(
                site_id=site_id,
                schema_version="2.0.0",
                input=record["input"],
                extraction=record["extraction"],
                provenance=record["provenance"],
                metrics=record["metrics"],
                run_metadata=record["run_metadata"],
            )
            await self._site_repo.save(quarry_record)
            sites_saved += 1
            job.sites_found = sites_saved
            await self._job_repo.update(job)

        await self._complete(job, sites_found=sites_saved)

    async def _complete(self, job: Job, sites_found: int) -> None:
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.sites_found = sites_found
        job.status_message = f"Completed — {sites_found} site(s) saved."
        job.completed_at = datetime.now(UTC)
        await self._job_repo.update(job)
        logger.info("Job %s completed — %d site(s) saved", job.id, sites_found)

    async def _fail(self, job: Job, error: str) -> None:
        job.status = JobStatus.FAILED
        job.error = error
        job.completed_at = datetime.now(UTC)
        await self._job_repo.update(job)
        logger.error("Job %s failed: %s", job.id, error)


def _coords_from_job(job: Job):
    from backend.domain.value_objects.coordinates import Coordinates

    return Coordinates(latitude=job.latitude, longitude=job.longitude, radius_km=job.radius_km)


def _site_id(candidate, job: Job) -> str:
    """Generate a stable site ID from candidate coordinates + job ID."""
    raw = f"{candidate.latitude:.6f}:{candidate.longitude:.6f}:{job.radius_km}:{job.id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:13]
