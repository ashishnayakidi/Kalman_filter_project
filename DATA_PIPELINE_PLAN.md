# Data Pipeline Architecture Plan

## Overview
Production-ready pipeline to transform 629k pickle files → fast, queryable analytics layer.

## Current State
- **Source**: 629,121 pickle files (774MB compressed)
- **Current Output**: Single 10GB CSV (`battery_dataset1_ekf.csv`)
- **Data**: ~80.5M rows, 128 time steps per file
- **Schema**: vehicle_id (car_id), voltage_V, current_A, temp_C, cycle_idx, etc.

## Proposed Architecture

### Phase 0: Freeze & Version Dataset ✅ **DO THIS FIRST**

**Create `dataset_v0/` structure:**
```
dataset_v0/
├── README.md                    # Source, license, processing date, scripts
├── manifest.json               # Total files, date range, columns, units, sampling rates
├── quality_report.json         # Missing rates, outlier stats, data quality metrics
└── scripts/                    # Copy of conversion scripts used
```

**Manifest Schema:**
```json
{
  "version": "v0",
  "source": "battery_dataset1.tar.gz",
  "license": "CC BY-NC-SA",
  "processing_date": "2024-11-16",
  "total_files": 629121,
  "total_rows": 80527488,
  "date_range": {"start": "...", "end": "..."},
  "columns": {
    "vehicle_id": {"type": "int", "description": "Car/vehicle identifier"},
    "ts": {"type": "datetime64[ns, UTC]", "description": "Timestamp (UTC)"},
    "current_A": {"type": "float64", "unit": "A", "description": "Current (positive=discharge)"},
    "voltage_V": {"type": "float64", "unit": "V", "description": "Voltage"},
    "temp_C": {"type": "float64", "unit": "°C", "description": "Temperature"},
    ...
  },
  "sampling_rate_hz": 1.0,
  "missing_rates": {"current_A": 0.001, "voltage_V": 0.0, ...},
  "scripts_used": ["convert_battery_dataset_full.py", "..."],
  "checksums": {"source": "...", "processed": "..."}
}
```

### Phase 1: Consolidate to Columnar Format ✅ **CRITICAL**

**Convert CSV → Parquet (partitioned):**
```
data/parquet/
├── timeseries/
│   ├── vehicle_id=1/
│   │   ├── date=2024-01-15/
│   │   │   └── part-00000.parquet
│   │   ├── date=2024-01-16/
│   │   │   └── part-00000.parquet
│   │   └── ...
│   ├── vehicle_id=2/
│   │   └── ...
│   └── ...
```

**Schema (Single Truth Table):**
```python
{
    "vehicle_id": int,           # From car_id
    "ts": datetime64[ns, UTC],   # Timestamp (UTC, monotonic per vehicle)
    "current_A": float64,        # Current (positive=discharge)
    "voltage_V": float64,        # Voltage
    "temp_C": float64,           # Temperature (°C)
    "soc_raw": float64,          # Raw SOC if available (optional)
    "soh_label": int,            # SOH label if available (optional)
    "cycle_id": int,             # Cycle index
    "trip_id": str,              # Trip/segment identifier (from charge_segment)
    "source_file": str,          # Original pickle filename
    "quality_flag": int,          # 0=good, 1=warning, 2=bad
    # Additional metadata
    "mileage": float64,
    "capacity": float64,
    "label": str,                # Classification label
    "voltage_2": float64,        # Additional voltage measurements
    "voltage_3": float64,
}
```

**Query Engine Options:**
1. **DuckDB** (Recommended for MVP)
   - Single-file DB, zero-config
   - Fast Parquet reads, SQL interface
   - Perfect for analytics queries
   - Can query Parquet directly without import

2. **Polars** (Alternative)
   - Lazy evaluation, very fast
   - Python-native, good for ETL
   - Less SQL-friendly than DuckDB

**Implementation:**
```python
# scripts/convert_to_parquet.py
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path

def csv_to_parquet(csv_path, output_dir, partition_cols=['vehicle_id', 'date']):
    """Convert CSV to partitioned Parquet."""
    # Read in chunks
    chunk_size = 1_000_000
    for chunk in pd.read_csv(csv_path, chunksize=chunk_size):
        # Add date column from ts
        chunk['date'] = pd.to_datetime(chunk['ts']).dt.date
        
        # Write partitioned
        pq.write_to_dataset(
            table=pa.Table.from_pandas(chunk),
            root_path=output_dir / 'timeseries',
            partition_cols=partition_cols,
            compression='snappy'
        )
```

### Phase 2: Data Quality Pass ✅ **ESSENTIAL**

**Checks to Implement:**
1. **Unit Validation:**
   - Current sign: all positive (discharge) or mixed?
   - Temperature: verify °C (not °F) - check for values >50°C
   - Voltage: 3.0-4.5V range for Li-ion
   
2. **Gaps & Outliers:**
   - NaN percentage per column
   - Current spikes: |ΔI/Δt| > threshold (e.g., 100 A/s)
   - Voltage jumps: |ΔV| > threshold (e.g., 0.5V in 1s)
   - Temperature outliers: < -20°C or > 60°C
   
3. **Clock Sanity:**
   - Monotonic timestamps within each vehicle
   - Timezone: ensure UTC
   - Gaps: flag large time gaps (>1 hour)
   - Duplicate timestamps: detect and handle
   
4. **Quality Flags:**
   ```python
   quality_flag = 0  # Good
   if has_nan or has_outlier:
       quality_flag = 1  # Warning
   if has_spike or has_duplicate_ts:
       quality_flag = 2  # Bad
   ```

**Output:** Quality report + flagged rows in Parquet

### Phase 3: Batch EKF Processing ✅ **CORE**

**Process Flow:**
```
timeseries/ → EKF → ekf_timeseries/
```

**EKF Output Schema:**
```python
{
    "vehicle_id": int,
    "ts": datetime64[ns, UTC],
    "soc": float64,              # EKF-estimated SOC (0.0-1.0)
    "v_pred": float64,          # Predicted voltage
    "residual": float64,         # V_measured - V_predicted
    "cov_soc": float64,          # SOC covariance
    "cov_vrc": float64,          # V_RC covariance
    "Q_now": float64,            # Current capacity estimate (Ah)
    "R0": float64,               # Series resistance (Ohm)
    "dcir_10pct": float64,       # DCIR at 10% SOC
    "dcir_50pct": float64,       # DCIR at 50% SOC
    "dcir_80pct": float64,       # DCIR at 80% SOC
    "confidence": float64,      # EKF confidence (0.0-1.0)
}
```

**Implementation:**
```python
# Process vehicle by vehicle, day by day
for vehicle_id in vehicle_ids:
    df = read_parquet(f"timeseries/vehicle_id={vehicle_id}/")
    
    # Initialize EKF for this vehicle
    ekf = BatteryEKF(...)
    
    # Process day by day
    for date in dates:
        df_day = df[df['date'] == date]
        
        results = []
        for _, row in df_day.iterrows():
            ekf_out = ekf.step(
                I_A=row['current_A'],
                V_V=row['voltage_V'],
                T_C=row['temp_C'],
                dt_s=row['dt_s']
            )
            results.append(ekf_out)
        
        # Write to partitioned Parquet
        write_parquet(results, f"ekf_timeseries/vehicle_id={vehicle_id}/date={date}/")
```

### Phase 4: Daily Summaries (Precomputed) ✅ **PERFORMANCE**

**Schema:**
```python
{
    "vehicle_id": int,
    "date": date,
    "energy_in_wh": float64,        # Charging energy
    "energy_out_wh": float64,       # Discharging energy
    "avg_temp_c": float64,
    "max_temp_c": float64,
    "min_temp_c": float64,
    "fast_charge_sessions": int,    # C-rate > 1C
    "idle_at_100pct_hours": float64,
    "min_soc": float64,
    "mean_soc": float64,
    "median_soc": float64,
    "charge_efficiency": float64,   # energy_out / energy_in
    "avg_dcir": float64,
    "soh_pct": float64,             # SOH estimate
    "residual_mean": float64,
    "residual_std": float64,
    "confidence_avg": float64,
}
```

**Compute from:**
- `timeseries/` for raw stats
- `ekf_timeseries/` for SOC/SOH/DCIR

### Phase 5: Prediction Metrics ✅ **VALUE-ADD**

**Metrics to Compute (Pick 3-5 for MVP):**

1. **Degradation So Far** (Essential)
   ```python
   degradation_pct = 1.0 - soh_pct
   ```

2. **Degradation Rate** (Essential)
   ```python
   # Robust linear fit: SOH vs time
   slope = robust_linear_fit(soh_series, time_series)
   degradation_rate_pct_per_month = slope * 30
   ```

3. **Remaining Useful Life (RUL)** (High Value)
   ```python
   target_soh = 0.80
   current_soh = latest_soh_pct
   if degradation_rate > 0:
       months_to_80pct = (current_soh - target_soh) / degradation_rate
       rul_months = np.clip(months_to_80pct, 6, 120)  # Cap 6-120 months
   else:
       rul_months = None  # Not degrading
   confidence = calculate_confidence(soh_history_length, residual_std)
   ```

4. **Range Loss** (User-Facing)
   ```python
   nominal_range_km = 400  # Vehicle-specific
   range_loss_km = (1.0 - soh_pct) * nominal_range_km
   current_range_km = soh_pct * nominal_range_km
   ```

5. **Charge Efficiency Trend** (Optional)
   ```python
   # Moving average of energy_in / energy_out ratio
   efficiency_trend = rolling_mean(energy_out / energy_in, window=30)
   ```

6. **Thermal Stress Index** (Optional)
   ```python
   # Weighted time above 45°C by SOC
   thermal_stress = sum(time_at_temp > 45°C) * soc_weight
   ```

7. **Recharge Habit Score** (Optional)
   ```python
   # Time at 100% SOC + high-C-rate sessions
   habit_score = (hours_at_100pct * 0.5) + (fast_charge_count * 0.5)
   ```

**Store in:** `prediction_metrics/vehicle_id=.../metrics.parquet`

### Phase 6: Backend API (FastAPI) ✅ **DELIVERY**

**Endpoints:**

1. **`GET /owner/state?vehicle_id={id}`**
   ```json
   {
     "vehicle_id": 1,
     "latest": {
       "soc": 0.85,
       "soh_pct": 0.92,
       "rul_months": 24.5,
       "degradation_pct": 0.08,
       "confidence": 0.95,
       "timestamp": "2024-11-16T10:30:00Z"
     }
   }
   ```

2. **`GET /owner/trends?vehicle_id={id}&start={date}&end={date}`**
   ```json
   {
     "soc_series": [...],      # Downsampled to 1 point/hour
     "soh_series": [...],     # Daily values
     "dcir_bins": {
       "10pct": [...],
       "50pct": [...],
       "80pct": [...]
     },
     "residual_stats": {
       "mean": 0.001,
       "std": 0.005
     }
   }
   ```

3. **`GET /owner/daily?vehicle_id={id}&date={date}`**
   - Returns daily_summaries row for that date

4. **`GET /report/weekly?vehicle_id={id}`**
   - Generates markdown + JSON bundle
   - Includes charts (base64 encoded or URLs)

**Query Implementation:**
```python
import duckdb

# Connect to Parquet files
conn = duckdb.connect()
conn.execute("""
    CREATE VIEW timeseries AS 
    SELECT * FROM read_parquet('data/parquet/timeseries/**/*.parquet')
""")

# Query
result = conn.execute("""
    SELECT vehicle_id, ts, soc, v_pred, residual
    FROM ekf_timeseries
    WHERE vehicle_id = ? AND ts BETWEEN ? AND ?
    ORDER BY ts
""", [vehicle_id, start_ts, end_ts]).df()
```

**Incremental ETL (Fetch Button):**
```python
@app.post("/fetch/trigger")
async def trigger_fetch():
    # Find new partitions since last run
    last_run = get_last_fetch_time()
    new_partitions = find_new_partitions(last_run)
    
    # Process only new data
    for partition in new_partitions:
        run_ekf(partition)
        update_daily_summaries(partition)
        update_prediction_metrics(partition)
    
    return {"processed": len(new_partitions)}
```

## Implementation Priority

### MVP (Week 1-2)
1. ✅ Phase 0: Freeze dataset + manifest
2. ✅ Phase 1: CSV → Parquet conversion (partitioned)
3. ✅ Phase 2: Basic data quality checks
4. ✅ Phase 3: Batch EKF (single vehicle, test)
5. ✅ Phase 6: Basic API (state endpoint only)

### Phase 2 (Week 3-4)
1. ✅ Phase 3: Full batch EKF (all vehicles)
2. ✅ Phase 4: Daily summaries
3. ✅ Phase 5: Top 3 prediction metrics (degradation, RUL, range loss)
4. ✅ Phase 6: Full API (trends, daily, weekly report)

### Phase 3 (Week 5+)
1. ✅ Phase 5: Remaining prediction metrics
2. ✅ Phase 6: Incremental ETL
3. ✅ Optimization: Query caching, indexing
4. ✅ Monitoring: Data quality dashboards

## Technology Stack

- **Storage**: Parquet (Snappy compression)
- **Query Engine**: DuckDB (recommended) or Polars
- **Backend**: FastAPI (already in use)
- **Processing**: Python + pandas/pyarrow
- **EKF**: Existing `agent/ekf.py`

## File Size Estimates

- **Current CSV**: 10GB
- **Parquet (compressed)**: ~2-3GB (5-6x compression)
- **EKF timeseries**: ~3-4GB
- **Daily summaries**: ~10MB (very small)
- **Total**: ~5-7GB (vs 10GB CSV)

## Benefits

1. **Query Speed**: 10-100x faster than CSV
2. **Storage**: 50% smaller with compression
3. **Scalability**: Partitioned = parallel queries
4. **Maintainability**: Versioned, documented
5. **Production-Ready**: Industry-standard format

## Considerations

1. **Timestamp Reconstruction**: Current data has `time_s` (relative), need to map to absolute UTC timestamps
2. **Vehicle ID Mapping**: Ensure consistent vehicle_id across all tables
3. **Incremental Processing**: Design for "new data only" updates
4. **Backup Strategy**: Parquet files are immutable - version them
5. **Query Performance**: Consider adding indexes (DuckDB handles this automatically)

## Next Steps

1. Create `dataset_v0/` structure
2. Write manifest generation script
3. Implement CSV → Parquet converter
4. Test with single vehicle partition
5. Scale to full dataset

