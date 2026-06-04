"""SQLAlchemy ORM models for the quarry extraction pipeline.

Two tables:
- jobs   : tracks the lifecycle of each extraction request.
- sites  : stores fully validated quarry records (full JSON in JSONB).

Denormalised columns on `sites` (official_name, operational_status) exist
only to support fast API filtering without unpacking the JSONB record.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class JobModel(Base):
    """Persisted state of an extraction job."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    radius_km: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sites_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_usd_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SiteModel(Base):
    """Persisted quarry record conforming to output schema v2.0.0."""

    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(8), nullable=False, default="2.0.0")
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    radius_km: Mapped[float] = mapped_column(Float, nullable=False)
    official_name: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    operational_status: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    record: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
