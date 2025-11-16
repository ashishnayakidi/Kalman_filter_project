"""Parquet data query endpoints for processed battery data."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from pathlib import Path
import duckdb
import pandas as pd
from datetime import datetime

router = APIRouter()

# Data directories (using dev subset for now)
BASE_DATA_DIR = Path("data")
PREDICTION_METRICS_DIR = BASE_DATA_DIR / "prediction_metrics" / "prediction_metrics"
DAILY_SUMMARIES_DIR = BASE_DATA_DIR / "daily_summaries" / "daily_summaries"
EKF_TIMESERIES_DIR = BASE_DATA_DIR / "ekf_output" / "ekf_timeseries"


def get_duckdb_connection():
    """Get a DuckDB connection."""
    return duckdb.connect()


@router.get("/prediction-metrics")
async def get_prediction_metrics(
    vehicle_id: Optional[int] = Query(None, description="Vehicle ID (default: first available)")
):
    """
    Get prediction metrics for a vehicle.
    
    Returns:
    - Current SOH, degradation rates, RUL, range loss, thermal stress, etc.
    """
    if not PREDICTION_METRICS_DIR.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Prediction metrics directory not found: {PREDICTION_METRICS_DIR}"
        )
    
    conn = get_duckdb_connection()
    
    try:
        # If no vehicle_id specified, get the first available
        if vehicle_id is None:
            vehicles_query = f"""
            SELECT DISTINCT vehicle_id 
            FROM read_parquet('{PREDICTION_METRICS_DIR}/**/*.parquet')
            ORDER BY vehicle_id
            LIMIT 1
            """
            result = conn.execute(vehicles_query).df()
            if len(result) == 0:
                raise HTTPException(status_code=404, detail="No prediction metrics found")
            vehicle_id = int(result.iloc[0]['vehicle_id'])
        
        # Get prediction metrics for the vehicle
        query = f"""
        SELECT *
        FROM read_parquet('{PREDICTION_METRICS_DIR}/**/*.parquet')
        WHERE vehicle_id = {vehicle_id}
        """
        
        df = conn.execute(query).df()
        
        if len(df) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No prediction metrics found for vehicle_id={vehicle_id}"
            )
        
        # Convert to dict (should be single row)
        metrics = df.iloc[0].to_dict()
        
        # Convert numpy types to Python native types
        for key, value in metrics.items():
            if pd.isna(value):
                metrics[key] = None
            elif isinstance(value, (pd.Timestamp, datetime)):
                metrics[key] = str(value)
            elif hasattr(value, 'item'):  # numpy scalar
                metrics[key] = value.item()
        
        return {
            "vehicle_id": vehicle_id,
            "metrics": metrics
        }
    
    finally:
        conn.close()


@router.get("/daily-summaries")
async def get_daily_summaries(
    vehicle_id: Optional[int] = Query(None, description="Vehicle ID (default: first available)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=10000, description="Maximum number of records to return")
):
    """
    Get daily summaries for a vehicle.
    
    Returns daily aggregated statistics including:
    - Energy in/out, charge efficiency
    - Temperature statistics
    - SOC/SOH metrics
    - Usage patterns
    """
    if not DAILY_SUMMARIES_DIR.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Daily summaries directory not found: {DAILY_SUMMARIES_DIR}"
        )
    
    conn = get_duckdb_connection()
    
    try:
        # If no vehicle_id specified, get the first available
        if vehicle_id is None:
            vehicles_query = f"""
            SELECT DISTINCT vehicle_id 
            FROM read_parquet('{DAILY_SUMMARIES_DIR}/**/*.parquet')
            ORDER BY vehicle_id
            LIMIT 1
            """
            result = conn.execute(vehicles_query).df()
            if len(result) == 0:
                raise HTTPException(status_code=404, detail="No daily summaries found")
            vehicle_id = int(result.iloc[0]['vehicle_id'])
        
        # Build query
        query = f"""
        SELECT *
        FROM read_parquet('{DAILY_SUMMARIES_DIR}/**/*.parquet')
        WHERE vehicle_id = {vehicle_id}
        """
        
        if start_date:
            query += f" AND date >= '{start_date}'"
        if end_date:
            query += f" AND date <= '{end_date}'"
        
        query += f" ORDER BY date LIMIT {limit}"
        
        df = conn.execute(query).df()
        
        if len(df) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No daily summaries found for vehicle_id={vehicle_id}"
            )
        
        # Convert to list of dicts
        summaries = []
        for _, row in df.iterrows():
            summary = row.to_dict()
            # Convert numpy types
            for key, value in summary.items():
                if pd.isna(value):
                    summary[key] = None
                elif isinstance(value, (pd.Timestamp, datetime)):
                    summary[key] = str(value)
                elif hasattr(value, 'item'):
                    summary[key] = value.item()
            summaries.append(summary)
        
        return {
            "vehicle_id": vehicle_id,
            "count": len(summaries),
            "summaries": summaries
        }
    
    finally:
        conn.close()


@router.get("/ekf-timeseries")
async def get_ekf_timeseries(
    vehicle_id: Optional[int] = Query(None, description="Vehicle ID (default: first available)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(1000, ge=1, le=100000, description="Maximum number of records to return")
):
    """
    Get EKF timeseries data for a vehicle.
    
    Returns detailed EKF outputs including:
    - SOC, SOH estimates
    - Voltage predictions and residuals
    - RC circuit states
    - Parameter estimates
    """
    if not EKF_TIMESERIES_DIR.exists():
        raise HTTPException(
            status_code=404,
            detail=f"EKF timeseries directory not found: {EKF_TIMESERIES_DIR}"
        )
    
    conn = get_duckdb_connection()
    
    try:
        # If no vehicle_id specified, get the first available
        if vehicle_id is None:
            vehicles_query = f"""
            SELECT DISTINCT vehicle_id 
            FROM read_parquet('{EKF_TIMESERIES_DIR}/**/*.parquet')
            ORDER BY vehicle_id
            LIMIT 1
            """
            result = conn.execute(vehicles_query).df()
            if len(result) == 0:
                raise HTTPException(status_code=404, detail="No EKF timeseries found")
            vehicle_id = int(result.iloc[0]['vehicle_id'])
        
        # Build query
        query = f"""
        SELECT *
        FROM read_parquet('{EKF_TIMESERIES_DIR}/**/*.parquet')
        WHERE vehicle_id = {vehicle_id}
        """
        
        if start_date:
            query += f" AND CAST(date AS DATE) >= CAST('{start_date}' AS DATE)"
        if end_date:
            query += f" AND CAST(date AS DATE) <= CAST('{end_date}' AS DATE)"
        
        query += f" ORDER BY time_s LIMIT {limit}"
        
        df = conn.execute(query).df()
        
        if len(df) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No EKF timeseries found for vehicle_id={vehicle_id}"
            )
        
        # Convert to list of dicts
        timeseries = []
        for _, row in df.iterrows():
            record = row.to_dict()
            # Convert numpy types and handle arrays
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None
                elif isinstance(value, (pd.Timestamp, datetime)):
                    record[key] = str(value)
                elif isinstance(value, (list, tuple)) or (hasattr(value, '__iter__') and not isinstance(value, str)):
                    # Handle arrays (like cov)
                    try:
                        if hasattr(value, 'tolist'):
                            record[key] = value.tolist()
                        else:
                            record[key] = list(value)
                    except:
                        record[key] = None
                elif hasattr(value, 'item'):
                    record[key] = value.item()
            timeseries.append(record)
        
        return {
            "vehicle_id": vehicle_id,
            "count": len(timeseries),
            "timeseries": timeseries
        }
    
    finally:
        conn.close()


@router.get("/vehicles")
async def list_vehicles():
    """
    List all available vehicles in the processed datasets.
    """
    conn = get_duckdb_connection()
    
    vehicles = set()
    
    try:
        # Check prediction metrics
        if PREDICTION_METRICS_DIR.exists():
            query = f"""
            SELECT DISTINCT vehicle_id 
            FROM read_parquet('{PREDICTION_METRICS_DIR}/**/*.parquet')
            """
            df = conn.execute(query).df()
            vehicles.update(df['vehicle_id'].tolist())
        
        # Check daily summaries
        if DAILY_SUMMARIES_DIR.exists():
            query = f"""
            SELECT DISTINCT vehicle_id 
            FROM read_parquet('{DAILY_SUMMARIES_DIR}/**/*.parquet')
            """
            df = conn.execute(query).df()
            vehicles.update(df['vehicle_id'].tolist())
        
        # Check EKF timeseries
        if EKF_TIMESERIES_DIR.exists():
            query = f"""
            SELECT DISTINCT vehicle_id 
            FROM read_parquet('{EKF_TIMESERIES_DIR}/**/*.parquet')
            """
            df = conn.execute(query).df()
            vehicles.update(df['vehicle_id'].tolist())
        
        return {
            "vehicles": sorted([int(v) for v in vehicles]),
            "count": len(vehicles)
        }
    
    finally:
        conn.close()

