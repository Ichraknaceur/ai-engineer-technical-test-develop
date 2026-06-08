"""
EXPLORATION SCRIPT — infrastructure/db/models.py
==================================================
Run with:  uv run python test_explore.py

Covers:
  - What SQLAlchemy ORM models are
  - JobModel columns and types
  - SiteModel columns and types
  - The difference between ORM models and domain entities
  - How the JSONB column works
"""

# ─── 1. What is an ORM model? ─────────────────────────────────────────────────
print("=" * 60)
print("STEP 1 — What is an ORM model?")
print("=" * 60)
print("""
  ORM = Object Relational Mapper.

  Instead of writing raw SQL like:
    INSERT INTO jobs (id, latitude, ...) VALUES (...)

  SQLAlchemy lets you work with Python objects:
    session.add(JobModel(id="j_1", latitude=48.8, ...))

  The ORM translates Python ↔ SQL automatically.
""")

from backend.infrastructure.db.models import Base, JobModel, SiteModel

print("  Our two tables:")
for table_name, table in Base.metadata.tables.items():
    cols = [c.name for c in table.columns]
    print(f"    {table_name:8} → columns: {cols}")
print()


# ─── 2. JobModel ──────────────────────────────────────────────────────────────
print("=" * 60)
print("STEP 2 — JobModel (table: jobs)")
print("=" * 60)

print("  Inspecting each column:\n")
for col in JobModel.__table__.columns:
    nullable = "nullable" if col.nullable else "NOT NULL"
    default  = f"default={col.default.arg}" if col.default is not None else ""
    print(f"    {col.name:20} {str(col.type):30} {nullable:10} {default}")

print()
print("  Creating a JobModel instance (in memory only — no DB yet):")

from datetime import UTC, datetime

job_row = JobModel(
    id="j_abc123",
    latitude=48.8566,
    longitude=2.3522,
    radius_km=50.0,
    status="pending",
    progress=0,
    status_message="",
    sites_found=0,
    created_at=datetime.now(UTC),
)

print(f"    id         = {job_row.id}")
print(f"    latitude   = {job_row.latitude}")
print(f"    status     = {job_row.status}")
print(f"    progress   = {job_row.progress}")
print(f"    created_at = {job_row.created_at}")
print()

print("  Important: JobModel is NOT the same as the Job domain entity.")
print("""
    Job (domain entity)      JobModel (ORM model)
    ────────────────────     ────────────────────
    Pure Python dataclass    Tied to SQLAlchemy
    No DB knowledge          Knows about tables/columns
    Used in business logic   Used only in db/repositories
    Has JobStatus enum       Has plain string 'pending'

    The repository converts between the two.
""")


# ─── 3. SiteModel ─────────────────────────────────────────────────────────────
print("=" * 60)
print("STEP 3 — SiteModel (table: sites)")
print("=" * 60)

print("  Inspecting each column:\n")
for col in SiteModel.__table__.columns:
    nullable = "nullable" if col.nullable else "NOT NULL"
    index    = "indexed" if col.index else ""
    print(f"    {col.name:20} {str(col.type):30} {nullable:10} {index}")

print()
print("  The most important column is 'record' (JSONB):")
print("""
    record: Mapped[dict] = mapped_column(JSONB)

    JSONB stores the full validated QuarryRecord as JSON in PostgreSQL.
    This means:
      ✓ No migrations needed when the schema evolves
      ✓ The full record is always available in one query
      ✗ You can't filter by nested fields without unpacking

    That's why we have denormalised columns:
      official_name      ← copied from record.extraction.official_name.value
      operational_status ← copied from record.extraction.operational_status.value

    These allow fast SQL filtering without touching JSONB:
      SELECT * FROM sites WHERE operational_status = 'active'
""")

print("  Creating a SiteModel instance (in memory only — no DB yet):")

site_row = SiteModel(
    id="a1f3c8d27e4b9",
    job_id="j_abc123",
    schema_version="2.0.0",
    latitude=48.9012,
    longitude=2.1034,
    radius_km=50.0,
    official_name="Carrière de Vignats",
    operational_status=None,
    record={
        "site_id": "a1f3c8d27e4b9",
        "schema_version": "2.0.0",
        "extraction": {
            "official_name": {
                "value": "Carrière de Vignats",
                "confidence": 0.92,
                "evidence": [],
            }
        },
    },
    created_at=datetime.now(UTC),
)

print(f"    id                 = {site_row.id}")
print(f"    job_id             = {site_row.job_id}")
print(f"    official_name      = {site_row.official_name}  ← denormalised")
print(f"    operational_status = {site_row.operational_status}   ← denormalised (None = abstained)")
print(f"    record type        = {type(site_row.record)}  ← full JSON stored in JSONB")
print(f"    record keys        = {list(site_row.record.keys())}")
print()


# ─── 4. Base.metadata ─────────────────────────────────────────────────────────
print("=" * 60)
print("STEP 4 — Base.metadata (used by Alembic)")
print("=" * 60)
print("""
  Base.metadata knows about ALL tables defined with DeclarativeBase.
  Alembic reads Base.metadata to:
    - Generate migration scripts (alembic revision --autogenerate)
    - Apply migrations (alembic upgrade head)
    - Roll back migrations (alembic downgrade -1)

  This is why env.py has:
    target_metadata = Base.metadata
""")

print(f"  Tables registered in Base.metadata: {list(Base.metadata.tables.keys())}")
print()


# ─── 5. SQL generated ─────────────────────────────────────────────────────────
print("=" * 60)
print("STEP 5 — The SQL that SQLAlchemy would generate")
print("=" * 60)
print("  CREATE TABLE statements for our models:\n")

from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable

sync_engine = create_engine("postgresql://x/x", strategy="mock", executor=lambda s, *a, **kw: print(f"    {s}"))
Base.metadata.create_all(sync_engine)
print()

print("=" * 60)
print("DONE — infrastructure/db/models.py explored")
print("=" * 60)
