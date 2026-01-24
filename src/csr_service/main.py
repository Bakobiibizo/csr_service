"""FastAPI application entry point.

The lifespan handler loads standards from disk, initializes TF-IDF retrievers
for each standards set, and creates the model client. All state is stored on
app.state for access by route handlers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .engine.model_client import ModelClient
from .logging import logger
from .routes import health_router, review_router, standards_router
from .standards.loader import load_standards
from .standards.retriever import StandardsRetriever


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


app = FastAPI(title="Content Standards Review Service", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(standards_router)
app.include_router(review_router)
