"""Application service for quarry site queries.

SiteService is the concrete implementation of the ISiteService inbound port.
It delegates all persistence to the ISiteRepository outbound port.
"""

from backend.domain.entities.quarry import QuarryRecord
from backend.ports.outbound.site_repository import ISiteRepository


class SiteService:
    """Exposes read operations on quarry site records to the API layer.

    Args:
        site_repo: Adapter for retrieving and listing QuarryRecord entities.
    """

    def __init__(self, site_repo: ISiteRepository) -> None:
        self._site_repo = site_repo

    async def get(self, site_id: str) -> QuarryRecord | None:
        """Retrieve a single quarry record by its stable site ID.

        Args:
            site_id: The 13-char hash identifier of the site.

        Returns:
            The QuarryRecord if found, None otherwise.
        """
        raise NotImplementedError

    async def list(
        self,
        q: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[int, list[QuarryRecord]]:
        """List quarry records with optional filtering and pagination.

        Args:
            q:         Optional text search on the official name.
            status:    Optional filter on operational_status.
            page:      1-based page number.
            page_size: Number of records per page.

        Returns:
            A tuple of (total_count, records_on_this_page).
        """
        raise NotImplementedError
