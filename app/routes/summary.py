"""Summary endpoints (minute and daily)."""
from fastapi import APIRouter
from app.core.models import MinuteRollupResponse, DailySummaryResponse
from agent.scoring import minute_rollup, daily_summary

router = APIRouter()


@router.get("/minute", response_model=MinuteRollupResponse)
async def get_minute_summary():
    """Get minute-level rollup."""
    rollup = minute_rollup()
    return MinuteRollupResponse(**rollup)


@router.get("/daily", response_model=DailySummaryResponse)
async def get_daily_summary():
    """Get daily summary."""
    summary = daily_summary()
    return DailySummaryResponse(**summary)

