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
    audit,
    batches,
    cameras,
    centres,
    dashboard,
    events,
    inventory,
    reports,
    stream,
    trades,
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

# Register API Routers under both root and /api prefixes to reconcile Vercel service rewrites
api_routers = [
    events.router,
    attendance.router,
    centres.router,
    cameras.router,
    stream.router,
    inventory.router,
    batches.router,
    alerts.router,
    audit.router,
    reports.router,
    trades.router,
    dashboard.router,
]

for router_item in api_routers:
    app.include_router(router_item)
    app.include_router(router_item, prefix="/api")


@app.get("/", tags=["Health & Info"])
@app.get("/api", tags=["Health & Info"])
def root():
    return {
        "app": settings.app_name,
        "version": "1.0.0",
        "status": "online",
        "documentation": "/docs",
        "privacy_policy": "Strict: Zero facial identification. Aggregated counts only.",
    }


@app.get("/health", tags=["Health & Info"])
@app.get("/api/health", tags=["Health & Info"])
def health_check():
    return {"status": "healthy"}
