"""FastAPI application entry point.

Routers are registered here. Dependency injection (services, repositories)
is wired through FastAPI's Depends mechanism in each router module.
"""

from fastapi import FastAPI

app = FastAPI(title="Quarry Extraction API", version="1.0.0")
