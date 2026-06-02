"""Outbound port for quarry site persistence.

Any adapter that stores and retrieves QuarryRecord entities must satisfy this
protocol. Current implementation: PostgresSiteRepository (SQLAlchemy + asyncpg).
"""

from typing import Protocol

from backend.domain.entities.quarry import QuarryRecord


class ISiteRepository(Protocol):
    """Contract for persisting and querying quarry site records."""

    async def save(self, record: QuarryRecord) -> None:
        """Persist a validated quarry record.

        Args:
            record: The fully validated QuarryRecord to store.
        """
        ...

    async def get(self, site_id: str) -> QuarryRecord | None:
        """Retrieve a quarry record by its stable site ID.

        Args:
            site_id: The 13-char hash identifier of the site.

        Returns:
            The QuarryRecord if found, None otherwise.
        """
        ...

    async def list(
        self,
        q: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[int, list[QuarryRecord]]:
        """List quarry records with optional filtering and pagination.

        Args:
            q:         Optional text search against the official name.
            status:    Optional filter on operational_status value.
            page:      1-based page number.
            page_size: Number of records per page.

        Returns:
            A tuple of (total_count, records_on_this_page).
        """
        ...
