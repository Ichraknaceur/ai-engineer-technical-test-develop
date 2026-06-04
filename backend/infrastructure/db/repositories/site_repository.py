"""PostgreSQL implementation of ISiteRepository using SQLAlchemy async."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.entities.quarry import QuarryRecord
from backend.infrastructure.db.models import SiteModel


class PostgresSiteRepository:
    """Reads and writes QuarryRecord entities to the PostgreSQL sites table.

    Args:
        session: An active async SQLAlchemy session (injected per-request).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: QuarryRecord) -> None:
        """Insert a new site row (full JSON stored in JSONB column)."""
        official_name = (
            record.extraction.get("official_name", {}).get("value")
            if isinstance(record.extraction, dict)
            else None
        )
        operational_status = (
            record.extraction.get("operational_status", {}).get("value")
            if isinstance(record.extraction, dict)
            else None
        )
        model = SiteModel(
            id=record.site_id,
            job_id=record.run_metadata.get("run_id", ""),
            schema_version=record.schema_version,
            latitude=record.input.get("latitude", 0.0),
            longitude=record.input.get("longitude", 0.0),
            radius_km=record.input.get("radius_km", 0.0),
            official_name=official_name,
            operational_status=operational_status,
            record={
                "site_id": record.site_id,
                "schema_version": record.schema_version,
                "input": record.input,
                "extraction": record.extraction,
                "provenance": record.provenance,
                "metrics": record.metrics,
                "run_metadata": record.run_metadata,
            },
        )
        self._session.add(model)
        await self._session.commit()

    async def get(self, site_id: str) -> QuarryRecord | None:
        """Return the QuarryRecord for site_id, or None if not found."""
        result = await self._session.execute(select(SiteModel).where(SiteModel.id == site_id))
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def list(
        self,
        q: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[int, list[QuarryRecord]]:
        """Return a paginated, optionally filtered list of QuarryRecords."""
        base = select(SiteModel)
        if q:
            base = base.where(SiteModel.official_name.ilike(f"%{q}%"))
        if status:
            base = base.where(SiteModel.operational_status == status)

        count_result = await self._session.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        rows_result = await self._session.execute(base.offset(offset).limit(page_size))
        records = [self._to_entity(row) for row in rows_result.scalars()]
        return total, records

    @staticmethod
    def _to_entity(model: SiteModel) -> QuarryRecord:
        raw = model.record
        return QuarryRecord(
            site_id=raw["site_id"],
            schema_version=raw["schema_version"],
            input=raw["input"],
            extraction=raw["extraction"],
            provenance=raw["provenance"],
            metrics=raw["metrics"],
            run_metadata=raw["run_metadata"],
        )
