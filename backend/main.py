"""StratOS FastAPI application - AI Consulting Operating System backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from backend.database import init_db
from backend.api.routers import router as engagements_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle events."""
    logger.info("Starting StratOS backend...")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down StratOS backend...")


app = FastAPI(
    title="StratOS API",
    description="AI Consulting Operating System - Backend API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(engagements_router, prefix="/api/v1", tags=["engagements"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "stratos-api", "version": "0.1.0"}
