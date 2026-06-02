"""Main pipeline orchestrator that runs all extraction stages for a given job."""

from backend.ports.outbound.discoverer import IDiscoverer
from backend.ports.outbound.extractor import IExtractor
from backend.ports.outbound.job_repository import IJobRepository
from backend.ports.outbound.scraper import IScraper
from backend.ports.outbound.site_repository import ISiteRepository


class ExtractionPipeline:
    """Orchestrates the full quarry extraction pipeline for a single job.

    Stages executed in order:
    1. Discovery  — find quarry candidates in the search area.
    2. Scraping   — fetch and clean source pages for each candidate.
    3. Extraction — call the LLM to extract grounded fields from each page.
    4. Reconciliation — merge multi-source results, resolve conflicts.
    5. Validation — validate the final record against JSON Schema v2.0.0.
    6. Persistence — store the validated record and mark the job complete.

    All dependencies are injected so they can be swapped freely in tests.

    Args:
        discoverer: Adapter for finding quarry candidates.
        scraper:    Adapter for fetching and cleaning web pages.
        extractor:  Adapter for LLM-based field extraction.
        job_repo:   Adapter for updating job progress and status.
        site_repo:  Adapter for persisting final quarry records.
    """

    def __init__(
        self,
        discoverer: IDiscoverer,
        scraper: IScraper,
        extractor: IExtractor,
        job_repo: IJobRepository,
        site_repo: ISiteRepository,
    ) -> None:
        self._discoverer = discoverer
        self._scraper = scraper
        self._extractor = extractor
        self._job_repo = job_repo
        self._site_repo = site_repo

    async def run(self, job_id: str) -> None:
        """Execute all pipeline stages for the given job.

        Loads the job from the repository, runs each stage sequentially,
        and updates the job's status and progress throughout.
        On any unrecoverable error, marks the job as FAILED with an error message.

        Args:
            job_id: Unique identifier of the job to process.
        """
        raise NotImplementedError
