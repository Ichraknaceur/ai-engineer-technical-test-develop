"""FastAPI dependencies that provide application-layer services.

Each function assembles the concrete adapters and wires them into the
application service. Routers depend on these, not on concrete classes.
"""

from typing import Annotated

from fastapi import Depends

from backend.application.services.job_service import JobService
from backend.application.services.site_service import SiteService
from backend.infrastructure.api.dependencies.db import DbSession
from backend.infrastructure.db.repositories.job_repository import PostgresJobRepository
from backend.infrastructure.db.repositories.site_repository import PostgresSiteRepository
from backend.infrastructure.worker.stub_queue import StubTaskQueue


def get_job_service(session: DbSession) -> JobService:
    """Build a JobService wired to Postgres and the stub task queue."""
    return JobService(
        job_repo=PostgresJobRepository(session),
        queue=StubTaskQueue(),
    )


def get_site_service(session: DbSession) -> SiteService:
    """Build a SiteService wired to Postgres."""
    return SiteService(site_repo=PostgresSiteRepository(session))


JobServiceDep = Annotated[JobService, Depends(get_job_service)]
SiteServiceDep = Annotated[SiteService, Depends(get_site_service)]
