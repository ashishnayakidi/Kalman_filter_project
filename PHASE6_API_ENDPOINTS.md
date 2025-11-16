# Phase 6: Backend API for Parquet Data

## Overview

Phase 6 adds API endpoints to query processed Parquet data, focusing on **prediction metrics** for the 1-vehicle development subset.

## New Endpoints

All endpoints are under the `/data` prefix:

### 1. `/data/vehicles`
**GET** - List all available vehicles in processed datasets

**Response:**
```json
{
  "vehicles": [0],
  "count": 1
}
```

### 2. `/data/prediction-metrics` ⭐ **Main Endpoint**
**GET** - Get prediction metrics for a vehicle

**Query Parameters:**
- `vehicle_id` (optional): Vehicle ID (defaults to first available)

**Response:**
```json
{
  "vehicle_id": 0,
  "metrics": {
    "current_soh_pct": 1.0,
    "degradation_so_far_pct": 0.0,
    "degradation_rate_pct_per_month": -0.0,
    "degradation_rate_pct_per_year": -0.0,
    "degradation_trend": "stable",
    "rul_months": null,
    "rul_years": null,
    "rul_confidence": 0.0,
    "rul_status": "not_degrading",
    "range_loss_km": 0.0,
    "current_range_km": 400.0,
    "nominal_range_km": 400.0,
    "charge_efficiency_trend": 1.0,
    "thermal_stress_index": 972.08,
    "recharge_habit_score": 0.0006,
    "data_points": 1286,
    "date_range_days": 642
  }
}
```

### 3. `/data/daily-summaries`
**GET** - Get daily summaries for a vehicle

**Query Parameters:**
- `vehicle_id` (optional): Vehicle ID
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)
- `limit` (default: 100): Maximum records to return

**Response:**
```json
{
  "vehicle_id": 0,
  "count": 5,
  "summaries": [
    {
      "date": "2021-10-05",
      "energy_in_kwh": 2.5,
      "energy_out_kwh": 2.3,
      "charge_efficiency": 0.92,
      ...
    }
  ]
}
```

### 4. `/data/ekf-timeseries`
**GET** - Get detailed EKF timeseries data

**Query Parameters:**
- `vehicle_id` (optional): Vehicle ID
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)
- `limit` (default: 1000): Maximum records to return

**Response:**
```json
{
  "vehicle_id": 0,
  "count": 10,
  "timeseries": [
    {
      "time_s": 0.0,
      "soc": 0.95,
      "soh": 1.0,
      "v_pred": 3.7,
      "residual": 0.01,
      ...
    }
  ]
}
```

## Usage

### Start the API Server

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

### Access API Documentation

Visit: http://localhost:8000/docs

### Example Requests

```bash
# Get prediction metrics
curl "http://localhost:8000/data/prediction-metrics?vehicle_id=0"

# Get daily summaries
curl "http://localhost:8000/data/daily-summaries?vehicle_id=0&limit=10"

# Get EKF timeseries
curl "http://localhost:8000/data/ekf-timeseries?vehicle_id=0&limit=100"
```

### Test Script

Run the HTTP test script (requires server to be running):

```bash
source .venv/bin/activate
python scripts/test_parquet_api_http.py
```

## Data Sources

The endpoints query Parquet files from:

- **Prediction Metrics**: `data/prediction_metrics/prediction_metrics/`
- **Daily Summaries**: `data/daily_summaries/daily_summaries/`
- **EKF Timeseries**: `data/ekf_output/ekf_timeseries/`

All data is partitioned by `vehicle_id` for fast queries using DuckDB.

## Implementation Details

- **FastAPI** with async endpoints
- **DuckDB** for fast Parquet queries (10-100x faster than CSV)
- **Automatic type conversion** (numpy types → Python native types)
- **Error handling** with proper HTTP status codes
- **Default vehicle selection** if `vehicle_id` not specified

## Current Status

✅ **Phase 6 Complete** - All endpoints implemented and tested

- Using 1-vehicle dev subset (vehicle_id=0)
- Prediction metrics endpoint working
- Daily summaries endpoint working
- EKF timeseries endpoint working
- Vehicle listing endpoint working

## Next Steps

1. **Test with real frontend** - Connect frontend to these endpoints
2. **Add authentication** - If needed for production
3. **Add caching** - For frequently accessed data
4. **Scale to more vehicles** - When ready to process full dataset

