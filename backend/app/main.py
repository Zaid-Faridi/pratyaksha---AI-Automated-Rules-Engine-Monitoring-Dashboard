"""
Pratyaksha Backend API Entrypoint.
FastAPI application with CORS, OpenAPI documentation, and automated database initialization.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import (
    alerts,
    attendance,
    batches,
    cameras,
    centres,
    dashboard,
    events,
    inventory,
    stream,
)
from app.streaming import stream_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure database tables exist
    init_db()
    yield
    # Shutdown logic: release all camera stream sessions
    stream_manager.stop_all()


app = FastAPI(
    title="Pratyaksha Backend API",
    description=(
        "AI Video-Analytics & Rules Engine for Monitoring Government Skilling Centres "
        "(MSDE Problem Statement 26245). Provides privacy-preserving attendance auditing, "
        "sanctioned infrastructure reconciliation, camera health monitoring, and compliance scoring."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for future dashboard / frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(events.router)
app.include_router(attendance.router)
app.include_router(centres.router)
app.include_router(cameras.router)
app.include_router(stream.router)
app.include_router(inventory.router)
app.include_router(batches.router)
app.include_router(alerts.router)
app.include_router(dashboard.router)


@app.get("/", tags=["Health & Info"])
def root():
    return {
        "app": settings.app_name,
        "version": "1.0.0",
        "status": "online",
        "documentation": "/docs",
        "privacy_policy": "Strict: Zero facial identification. Aggregated counts only.",
    }


@app.get("/health", tags=["Health & Info"])
def health_check():
    return {"status": "healthy"}
