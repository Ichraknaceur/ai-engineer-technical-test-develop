"""Inbound port exposing quarry site queries to the API layer.

The FastAPI routers depend on this protocol, not on the concrete SiteService,
keeping the infrastructure layer decoupled from the application layer.
"""

from typing import Protocol

from backend.domain.entities.quarry import QuarryRecord


class ISiteService(Protocol):
    """Contract for retrieving and listing quarry site records."""

    async def get(self, site_id: str) -> QuarryRecord | None:
        """Retrieve a single quarry record by its site ID.

        Args:
            site_id: The 13-char stable hash identifier of the site.

        Returns:
            The full QuarryRecord if found, None otherwise.
        """
        ...

    async def list(
        self,
        q: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[int, list[QuarryRecord]]:
        """List quarry records with optional text search, status filter, and pagination.

        Args:
            q:         Optional text search on the site name.
            status:    Optional filter on operational_status.
            page:      1-based page number.
            page_size: Records per page.

        Returns:
            A tuple of (total_count, records_on_this_page).
        """
        ...
