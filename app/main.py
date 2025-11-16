"""FastAPI main application."""
from fastapi import FastAPI
from app.routes import health, ekf, ingest, summary, report
from app.core.config import VERSION

app = FastAPI(
    title="Battery Agent API",
    description="Battery state estimation with EKF and LFM2-350M reporting",
    version=VERSION
)

# Include routers
app.include_router(health.router, tags=["health"])
# EKF routes at root level
app.include_router(ekf.router, tags=["ekf"])
# Ingest routes at root level
app.include_router(ingest.router, tags=["ingest"])
# Summary routes at root level
app.include_router(summary.router, tags=["summary"])
# Report routes
app.include_router(report.router, prefix="/report", tags=["report"])

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Battery Agent API",
        "version": VERSION,
        "docs": "/docs",
        "health": "/health"
    }

