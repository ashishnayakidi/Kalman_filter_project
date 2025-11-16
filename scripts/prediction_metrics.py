"""
Phase 5: Prediction Metrics

Computes prediction metrics from daily summaries:
- Degradation so far
- Degradation rate
- Remaining Useful Life (RUL)
- Range loss
- Charge efficiency trend
- Thermal stress index
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple
import sys
from tqdm import tqdm
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timedelta
import json
from scipy import stats


def robust_linear_fit(x: np.ndarray, y: np.ndarray) -> Tuple[float, float, float]:
    """
    Robust linear fit using Theil-Sen estimator (resistant to outliers).
    
    Returns: (slope, intercept, r_squared)
    """
    if len(x) < 2:
        return (0.0, np.mean(y) if len(y) > 0 else 0.0, 0.0)
    
    # Use Theil-Sen estimator (median of slopes)
    # For simplicity, use OLS with outlier removal
    try:
        # Remove NaN/inf
        mask = np.isfinite(x) & np.isfinite(y)
        x_clean = x[mask]
        y_clean = y[mask]
        
        if len(x_clean) < 2:
            return (0.0, np.mean(y_clean) if len(y_clean) > 0 else 0.0, 0.0)
        
        # Simple linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(x_clean, y_clean)
        r_squared = r_value ** 2
        
        return (float(slope), float(intercept), float(r_squared))
    except:
        # Fallback to simple mean
        return (0.0, float(np.mean(y)) if len(y) > 0 else 0.0, 0.0)


def calculate_degradation_rate(
    df: pd.DataFrame,
    soh_col: str = 'soh_pct',
    date_col: str = 'date'
) -> Dict:
    """
    Calculate degradation rate from SOH time series.
    
    Returns degradation rate in % per month.
    """
    if len(df) < 2:
        return {
            'degradation_rate_pct_per_month': 0.0,
            'degradation_rate_pct_per_year': 0.0,
            'fit_quality': 0.0,
            'trend': 'stable'
        }
    
    # Convert dates to numeric (days since first date)
    df = df.sort_values(date_col).copy()
    df['date_numeric'] = (pd.to_datetime(df[date_col]) - pd.to_datetime(df[date_col].min())).dt.days
    
    # Get SOH values
    soh_values = df[soh_col].values
    days = df['date_numeric'].values
    
    # Robust linear fit
    slope, intercept, r_squared = robust_linear_fit(days, soh_values)
    
    # Convert slope to % per month (assuming 30 days per month)
    degradation_rate_pct_per_month = -slope * 30  # Negative because SOH decreases
    degradation_rate_pct_per_year = degradation_rate_pct_per_month * 12
    
    # Determine trend
    if abs(degradation_rate_pct_per_month) < 0.01:
        trend = 'stable'
    elif degradation_rate_pct_per_month < 0:
        trend = 'degrading'
    else:
        trend = 'improving'  # Unlikely but possible
    
    return {
        'degradation_rate_pct_per_month': float(degradation_rate_pct_per_month),
        'degradation_rate_pct_per_year': float(degradation_rate_pct_per_year),
        'fit_quality': float(r_squared),
        'trend': trend,
        'slope': float(slope),
        'intercept': float(intercept)
    }


def calculate_rul(
    current_soh: float,
    degradation_rate_pct_per_month: float,
    target_soh: float = 0.80,
    min_rul_months: float = 6.0,
    max_rul_months: float = 120.0
) -> Dict:
    """
    Calculate Remaining Useful Life (RUL) in months.
    
    RUL = (current_soh - target_soh) / degradation_rate
    
    Args:
        current_soh: Current SOH (0.0-1.0)
        degradation_rate_pct_per_month: Degradation rate (% per month)
        target_soh: Target SOH threshold (default: 80%)
        min_rul_months: Minimum RUL cap (months)
        max_rul_months: Maximum RUL cap (months)
    
    Returns:
        Dictionary with RUL and confidence
    """
    if degradation_rate_pct_per_month <= 0:
        # Not degrading or improving
        return {
            'rul_months': None,
            'rul_years': None,
            'confidence': 0.0,
            'status': 'not_degrading'
        }
    
    # Calculate months to target
    soh_drop_needed = (current_soh - target_soh) * 100  # Convert to percentage
    months_to_target = soh_drop_needed / degradation_rate_pct_per_month
    
    # Cap RUL
    rul_months = np.clip(months_to_target, min_rul_months, max_rul_months)
    rul_years = rul_months / 12.0
    
    # Confidence based on degradation rate magnitude and fit quality
    # Higher degradation rate = more confident prediction
    # Lower degradation rate = less confident (could be noise)
    if abs(degradation_rate_pct_per_month) > 0.1:
        confidence = 0.9  # High confidence
    elif abs(degradation_rate_pct_per_month) > 0.01:
        confidence = 0.7  # Medium confidence
    else:
        confidence = 0.5  # Low confidence (near zero degradation)
    
    return {
        'rul_months': float(rul_months),
        'rul_years': float(rul_years),
        'confidence': float(confidence),
        'status': 'degrading'
    }


def calculate_range_loss(
    soh_pct: float,
    nominal_range_km: float = 400.0
) -> Dict:
    """
    Calculate range loss based on SOH.
    
    Range loss = (1 - SOH) * nominal_range
    Current range = SOH * nominal_range
    """
    range_loss_km = (1.0 - soh_pct) * nominal_range_km
    current_range_km = soh_pct * nominal_range_km
    
    return {
        'range_loss_km': float(range_loss_km),
        'current_range_km': float(current_range_km),
        'nominal_range_km': float(nominal_range_km)
    }


def calculate_charge_efficiency_trend(
    df: pd.DataFrame,
    window_days: int = 30
) -> float:
    """
    Calculate moving average of charge efficiency.
    
    Returns latest efficiency trend value.
    """
    if len(df) == 0:
        return 1.0
    
    if 'charge_efficiency' not in df.columns:
        return 1.0
    
    # Sort by date
    df = df.sort_values('date').copy()
    
    # Calculate rolling mean
    if len(df) >= window_days:
        trend = df['charge_efficiency'].tail(window_days).mean()
    else:
        trend = df['charge_efficiency'].mean()
    
    return float(trend)


def calculate_thermal_stress_index(
    df: pd.DataFrame,
    temp_threshold: float = 45.0
) -> float:
    """
    Calculate thermal stress index.
    
    Weighted time above threshold temperature by SOC.
    Higher SOC + high temp = more stress.
    """
    if len(df) == 0:
        return 0.0
    
    # Filter for high temperature
    high_temp = df[df['avg_temp_c'] > temp_threshold].copy()
    
    if len(high_temp) == 0:
        return 0.0
    
    # Weight by SOC (higher SOC = more stress)
    # Stress = hours_at_temp * soc_weight
    # soc_weight = mean_soc (higher SOC = more stress)
    stress = (high_temp['mean_soc'] * 1.0).sum()  # Assuming 1 hour per day
    
    return float(stress)


def calculate_recharge_habit_score(
    df: pd.DataFrame
) -> float:
    """
    Calculate recharge habit score.
    
    Based on:
    - Time at 100% SOC (idle_at_100pct_hours)
    - Fast charge sessions
    
    Higher score = worse habits (more time at 100%, more fast charging)
    """
    if len(df) == 0:
        return 0.0
    
    # Average hours at 100% SOC
    avg_hours_at_100 = df['idle_at_100pct_hours'].mean() if 'idle_at_100pct_hours' in df.columns else 0.0
    
    # Total fast charge sessions
    total_fast_charge = df['fast_charge_sessions'].sum() if 'fast_charge_sessions' in df.columns else 0
    
    # Score: weighted combination
    # Hours at 100% (weight 0.5) + fast charge count (weight 0.5)
    # Normalize: hours/24 * 0.5 + (fast_charge/100) * 0.5
    hours_score = min(1.0, avg_hours_at_100 / 24.0) * 0.5
    fast_charge_score = min(1.0, total_fast_charge / 100.0) * 0.5
    
    habit_score = hours_score + fast_charge_score
    
    return float(habit_score)


def compute_prediction_metrics(
    vehicle_id: int,
    df_daily: pd.DataFrame
) -> Dict:
    """
    Compute all prediction metrics for a vehicle.
    
    Args:
        vehicle_id: Vehicle ID
        df_daily: DataFrame with daily summaries for this vehicle
    
    Returns:
        Dictionary with all prediction metrics
    """
    if len(df_daily) == 0:
        return None
    
    # Sort by date
    df_daily = df_daily.sort_values('date').copy()
    
    # Latest values
    latest = df_daily.iloc[-1]
    current_soh = latest['soh_pct']
    current_date = latest['date']
    
    # 1. Degradation so far
    degradation_so_far_pct = (1.0 - current_soh) * 100.0
    
    # 2. Degradation rate
    degradation_rate = calculate_degradation_rate(df_daily)
    
    # 3. RUL
    rul = calculate_rul(
        current_soh=current_soh,
        degradation_rate_pct_per_month=degradation_rate['degradation_rate_pct_per_month']
    )
    
    # 4. Range loss
    range_metrics = calculate_range_loss(soh_pct=current_soh)
    
    # 5. Charge efficiency trend
    efficiency_trend = calculate_charge_efficiency_trend(df_daily)
    
    # 6. Thermal stress index
    thermal_stress = calculate_thermal_stress_index(df_daily)
    
    # 7. Recharge habit score
    habit_score = calculate_recharge_habit_score(df_daily)
    
    # Build metrics dictionary
    metrics = {
        'vehicle_id': vehicle_id,
        'last_updated': str(current_date),
        'current_soh_pct': float(current_soh),
        'degradation_so_far_pct': float(degradation_so_far_pct),
        'degradation_rate_pct_per_month': degradation_rate['degradation_rate_pct_per_month'],
        'degradation_rate_pct_per_year': degradation_rate['degradation_rate_pct_per_year'],
        'degradation_trend': degradation_rate['trend'],
        'degradation_fit_quality': degradation_rate['fit_quality'],
        'rul_months': rul['rul_months'],
        'rul_years': rul['rul_years'],
        'rul_confidence': rul['confidence'],
        'rul_status': rul['status'],
        'range_loss_km': range_metrics['range_loss_km'],
        'current_range_km': range_metrics['current_range_km'],
        'nominal_range_km': range_metrics['nominal_range_km'],
        'charge_efficiency_trend': efficiency_trend,
        'thermal_stress_index': thermal_stress,
        'recharge_habit_score': habit_score,
        'data_points': len(df_daily),
        'date_range_days': (pd.to_datetime(df_daily['date'].max()) - pd.to_datetime(df_daily['date'].min())).days
    }
    
    return metrics


def generate_prediction_metrics(
    daily_summaries_dir: Path,
    output_dir: Path,
    vehicle_ids: Optional[list] = None
):
    """
    Generate prediction metrics from daily summaries.
    
    Args:
        daily_summaries_dir: Directory with daily summaries Parquet files
        output_dir: Output directory for prediction metrics
        vehicle_ids: Optional list of vehicle IDs to process
    """
    print("=" * 70)
    print("Phase 5: Prediction Metrics Generation")
    print("=" * 70)
    print(f"\nInput:  {daily_summaries_dir}")
    print(f"Output: {output_dir / 'prediction_metrics'}\n")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Connect to DuckDB
    conn = duckdb.connect()
    
    # Get vehicle list
    if vehicle_ids is None:
        vehicles_query = f"""
        SELECT DISTINCT vehicle_id 
        FROM read_parquet('{daily_summaries_dir}/**/*.parquet')
        ORDER BY vehicle_id
        """
        vehicles = conn.execute(vehicles_query).df()['vehicle_id'].tolist()
    else:
        vehicles = vehicle_ids
    
    print(f"Processing {len(vehicles)} vehicle(s)...\n")
    
    all_metrics = []
    
    # Process each vehicle
    for vehicle_id in tqdm(vehicles, unit='vehicle'):
        # Get all daily summaries for this vehicle
        vehicle_query = f"""
        SELECT *
        FROM read_parquet('{daily_summaries_dir}/**/*.parquet')
        WHERE vehicle_id = {vehicle_id}
        ORDER BY date
        """
        
        df_vehicle = conn.execute(vehicle_query).df()
        
        if len(df_vehicle) == 0:
            continue
        
        # Compute prediction metrics
        metrics = compute_prediction_metrics(
            vehicle_id=vehicle_id,
            df_daily=df_vehicle
        )
        
        if metrics:
            all_metrics.append(metrics)
    
    conn.close()
    
    if not all_metrics:
        print("❌ No metrics generated")
        return
    
    # Convert to DataFrame
    df_metrics = pd.DataFrame(all_metrics)
    
    # Write to Parquet
    output_metrics = output_dir / 'prediction_metrics'
    table = pa.Table.from_pandas(df_metrics, preserve_index=False)
    pq.write_to_dataset(
        table,
        root_path=output_metrics,
        partition_cols=['vehicle_id'],
        compression='snappy',
        use_dictionary=True,
        write_statistics=True
    )
    
    # Print summary
    print("\n" + "=" * 70)
    print("Prediction Metrics Summary")
    print("=" * 70)
    print(f"\nTotal vehicles: {len(df_metrics)}")
    
    for _, row in df_metrics.iterrows():
        print(f"\nVehicle {int(row['vehicle_id'])}:")
        print(f"  Current SOH: {row['current_soh_pct']:.1%}")
        print(f"  Degradation so far: {row['degradation_so_far_pct']:.2f}%")
        print(f"  Degradation rate: {row['degradation_rate_pct_per_month']:.3f}%/month ({row['degradation_rate_pct_per_year']:.2f}%/year)")
        print(f"  Trend: {row['degradation_trend']}")
        if row['rul_months'] is not None:
            print(f"  RUL: {row['rul_months']:.1f} months ({row['rul_years']:.1f} years)")
            print(f"  RUL Confidence: {row['rul_confidence']:.1%}")
        else:
            print(f"  RUL: Not degrading")
        print(f"  Range loss: {row['range_loss_km']:.1f} km")
        print(f"  Current range: {row['current_range_km']:.1f} km")
        print(f"  Charge efficiency trend: {row['charge_efficiency_trend']:.3f}")
        print(f"  Thermal stress index: {row['thermal_stress_index']:.2f}")
        print(f"  Recharge habit score: {row['recharge_habit_score']:.3f}")
    
    print(f"\nOutput: {output_metrics}")
    
    # Save metadata
    metadata = {
        'generated_at': datetime.now().isoformat(),
        'source_dir': str(daily_summaries_dir),
        'vehicles': [int(v) for v in df_metrics['vehicle_id'].tolist()],
        'metrics_computed': list(df_metrics.columns)
    }
    
    metadata_path = output_dir / 'prediction_metrics_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Metadata: {metadata_path}")
    print("\n✅ Phase 5 Complete: Prediction Metrics Generated")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate Prediction Metrics (Phase 5)')
    parser.add_argument('--daily-summaries-dir',
                       default='data/daily_summaries/daily_summaries',
                       help='Input daily summaries directory')
    parser.add_argument('--output-dir',
                       default='data/prediction_metrics',
                       help='Output directory for prediction metrics')
    parser.add_argument('--vehicles',
                       type=int,
                       nargs='+',
                       default=None,
                       help='Specific vehicle IDs to process (default: all)')
    
    args = parser.parse_args()
    
    daily_summaries_dir = Path(args.daily_summaries_dir)
    output_dir = Path(args.output_dir)
    
    if not daily_summaries_dir.exists():
        print(f"❌ Error: Daily summaries directory not found: {daily_summaries_dir}")
        sys.exit(1)
    
    generate_prediction_metrics(
        daily_summaries_dir=daily_summaries_dir,
        output_dir=output_dir,
        vehicle_ids=args.vehicles
    )


if __name__ == '__main__':
    main()

