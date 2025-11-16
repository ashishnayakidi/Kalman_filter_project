"""Pydantic models for API requests/responses."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class TickRequest(BaseModel):
    """Request for /tick endpoint."""
    I_A: float = Field(..., description="Current in Amperes")
    V_V: float = Field(..., description="Voltage in Volts")
    T_C: float = Field(..., description="Temperature in Celsius")
    dt_s: float = Field(..., description="Time step in seconds")


class ReplayRequest(BaseModel):
    """Request for /replay endpoint."""
    csv_path: str = Field(..., description="Path to processed CSV file")


class QnARequest(BaseModel):
    """Request for /report/qna endpoint."""
    question: str = Field(..., description="Question about battery health")


class EKFStateResponse(BaseModel):
    """Response for EKF state."""
    soc: float
    v_rc: float
    cov: list
    params: Dict[str, float]


class TickResponse(BaseModel):
    """Response for /tick endpoint."""
    soc: float
    v_rc: float
    v_pred: float
    residual: float
    cov: list
    params: Dict[str, float]
    ocv: float
    temp_C: float


class HealthResponse(BaseModel):
    """Response for /health endpoint."""
    status: str
    version: str


class MinuteRollupResponse(BaseModel):
    """Response for /minute endpoint."""
    soc_mean: float
    soc_std: float
    residual_mean_mv: float
    residual_std_mv: float
    temp_mean_C: float
    tick_count: int


class DailySummaryResponse(BaseModel):
    """Response for /daily endpoint."""
    soh_pct: float
    dsoh_pct_per_week: float
    dcir_changes: Dict[str, Any]
    stress: Dict[str, Any]
    drift: Dict[str, Any]


class ReportResponse(BaseModel):
    """Response for report endpoints."""
    report: str
    summary: Optional[Dict[str, Any]] = None

