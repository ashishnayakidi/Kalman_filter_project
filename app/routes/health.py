"""Health check endpoint."""
from fastapi import APIRouter
from app.core.models import HealthResponse
from app.core.config import VERSION

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(status="ok", version=VERSION)

