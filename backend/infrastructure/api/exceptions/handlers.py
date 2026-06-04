"""HTTP exception handlers.

Translates domain errors into appropriate HTTP responses so that
routers never need to import or handle domain exceptions directly.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.domain.exceptions import (
    BudgetExceededError,
    DomainError,
    InvalidCoordinatesError,
    ScrapingNotAllowedError,
    ValidationError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all domain exception handlers on the FastAPI app."""

    @app.exception_handler(InvalidCoordinatesError)
    async def invalid_coordinates_handler(
        request: Request, exc: InvalidCoordinatesError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(BudgetExceededError)
    async def budget_exceeded_handler(request: Request, exc: BudgetExceededError) -> JSONResponse:
        return JSONResponse(status_code=402, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(ScrapingNotAllowedError)
    async def scraping_not_allowed_handler(
        request: Request, exc: ScrapingNotAllowedError
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
