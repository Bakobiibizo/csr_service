"""FastAPI application entry point.

The lifespan handler loads standards from disk, initializes TF-IDF retrievers
for each standards set, and creates the model client. All state is stored on
app.state for access by route handlers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .engine.model_client import ModelClient
from .logging import logger, print_settings
from .routes import health_router, review_router, standards_router
from .standards.loader import load_standards
from .standards.retriever import StandardsRetriever

logger.info("Starting CSR Service")

# Print settings with sensitive data masked
print_settings(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load standards
    standards_sets = load_standards(settings.standards_dir)
    app.state.standards_sets = standards_sets
    logger.info(f"Loaded {len(standards_sets)} standards set(s)")

    # Initialize retrievers
    retrievers = {}
    for set_id, ss in standards_sets.items():
        retrievers[set_id] = StandardsRetriever(ss)
    app.state.retrievers = retrievers

    # Initialize model client
    app.state.model_client = ModelClient()
    logger.info(f"Model client initialized: {settings.ollama_base_url} / {settings.model_id}")

    yield


# Initialize FastAPI app
app = FastAPI(title="Content Standards Review Service", version="0.1.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled request failure")
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "Internal service error"}},
    )


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(health_router)
app.include_router(standards_router)
app.include_router(review_router)
