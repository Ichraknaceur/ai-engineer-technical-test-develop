"""FastAPI dependency for database session injection.

Usage in a router:
    @router.get("/example")
    async def my_endpoint(session: DbSession) -> ...:
        result = await session.execute(...)
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.db.session import get_session

DbSession = Annotated[AsyncSession, Depends(get_session)]
