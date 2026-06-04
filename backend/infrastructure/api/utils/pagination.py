"""Pagination helpers shared across list endpoints."""

from typing import Annotated

from fastapi import Query


class PaginationParams:
    """Common pagination query parameters injected via FastAPI Depends."""

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
        page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    ) -> None:
        self.page = page
        self.page_size = page_size
