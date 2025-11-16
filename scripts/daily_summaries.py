"""
Phase 4: Daily Summaries (Precomputed)

Aggregates EKF timeseries data into daily summaries per vehicle.
Precomputed statistics for fast queries and dashboards.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional
import sys
from tqdm import tqdm
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def calculate_energy(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate energy in/out for a day.
    
    Energy = sum(I * V * dt) in Wh
    """
    # Energy calculation: E = sum(I * V * dt) / 3600 (convert to Wh)
    df = df.copy()
    
    # Get dt_s (default to 1.0 if not present)
    if 'dt_s' not in df.columns:
        # Calculate from time_s differences, or default to 1.0
        if 'time_s' in df.columns:
            df['dt_s'] = df['time_s'].diff().fillna(1.0)
        else:
            df['dt_s'] = 1.0
    
    # Calculate power: P = I * V (Watts)
    df['power_W'] = df['I_A'] * df['V_V']
    
    # Energy: E = P * dt (Joules), convert to Wh
    df['energy_Wh'] = df['power_W'] * df['dt_s'] / 3600.0
    
    # Separate charge (negative current = charging) and discharge (positive current)
    # Note: In our dataset, current is positive for discharge
    energy_out = df[df['I_A'] > 0]['energy_Wh'].sum()  # Discharge (energy out)
    energy_in = abs(df[df['I_A'] < 0]['energy_Wh'].sum())  # Charge (energy in, make positive)
    
    # If no charging, energy_in = 0
    if energy_in == 0:
        energy_in = 0.0
    
    return {
        'energy_in_wh': float(energy_in),
        'energy_out_wh': float(energy_out)
    }


def calculate_charge_efficiency(energy_in: float, energy_out: float) -> float:
    """Calculate charge efficiency: energy_out / energy_in."""
    if energy_in > 0:
        return float(energy_out / energy_in)
    return 1.0  # If no charging, assume 100% (or undefined)


def identify_fast_charge_sessions(df: pd.DataFrame, capacity_ah: float = 2.0) -> int:
    """
    Identify fast charge sessions (C-rate > 1C).
    
    C-rate = I / Q_nominal
    Fast charge: C-rate > 1.0
    """
    if len(df) == 0:
        return 0
    
    # Calculate C-rate
    df = df.copy()
    df['c_rate'] = np.abs(df['I_A']) / capacity_ah
    
    # Fast charge: C-rate > 1.0 and current < 0 (charging)
    fast_charge_mask = (df['c_rate'] > 1.0) & (df['I_A'] < 0)
    
    # Count distinct charge sessions (group by consecutive fast charge periods)
    if fast_charge_mask.sum() == 0:
        return 0
    
    # Simple: count transitions from non-fast to fast
    fast_charge_df = df[fast_charge_mask].copy()
    fast_charge_df = fast_charge_df.sort_values('time_s')
    
    # Count distinct sessions (group by cycle or time gaps > 1 hour)
    if len(fast_charge_df) == 0:
        return 0
    
    # Count unique cycles with fast charge
    sessions = fast_charge_df['cycle_idx'].nunique()
    
    return int(sessions)


def calculate_idle_at_100pct(df: pd.DataFrame) -> float:
    """Calculate hours spent at 100% SOC (idle time)."""
    # Filter for SOC >= 0.99 (essentially 100%)
    high_soc = df[df['soc'] >= 0.99].copy()
    
    if len(high_soc) == 0:
        return 0.0
    
    # Get dt_s (default to 1.0 if not present)
    if 'dt_s' not in high_soc.columns:
        if 'time_s' in high_soc.columns:
            high_soc['dt_s'] = high_soc['time_s'].diff().fillna(1.0)
        else:
            high_soc['dt_s'] = 1.0
    
    # Sum time spent at high SOC
    total_seconds = high_soc['dt_s'].sum()
    total_hours = total_seconds / 3600.0
    
    return float(total_hours)


def aggregate_daily_summary(
    vehicle_id: int,
    date: str,
    df_day: pd.DataFrame
) -> Dict:
    """
    Aggregate daily summary from EKF timeseries data.
    
    Args:
        vehicle_id: Vehicle ID
        date: Date string (YYYY-MM-DD)
        df_day: DataFrame with all rows for this vehicle/date
    
    Returns:
        Dictionary with daily summary statistics
    """
    if len(df_day) == 0:
        return None
    
    # Energy calculations
    energy = calculate_energy(df_day)
    charge_efficiency = calculate_charge_efficiency(
        energy['energy_in_wh'],
        energy['energy_out_wh']
    )
    
    # Temperature statistics
    temp_stats = {
        'avg_temp_c': float(df_day['T_C'].mean()),
        'max_temp_c': float(df_day['T_C'].max()),
        'min_temp_c': float(df_day['T_C'].min())
    }
    
    # Fast charge sessions
    capacity_ah = df_day.get('Q_now', pd.Series([2.0])).iloc[0] if 'Q_now' in df_day.columns else 2.0
    fast_charge_sessions = identify_fast_charge_sessions(df_day, capacity_ah)
    
    # Idle at 100% SOC
    idle_at_100pct_hours = calculate_idle_at_100pct(df_day)
    
    # SOC statistics
    soc_stats = {
        'min_soc': float(df_day['soc'].min()),
        'mean_soc': float(df_day['soc'].mean()),
        'median_soc': float(df_day['soc'].median()),
        'max_soc': float(df_day['soc'].max())
    }
    
    # SOH statistics
    if 'soh_pct' in df_day.columns:
        soh_pct = float(df_day['soh_pct'].mean())  # Average SOH for the day
    else:
        soh_pct = 1.0  # Default if not available
    
    # DCIR statistics (average of available DCIR values)
    dcir_values = []
    for col in ['dcir_10pct', 'dcir_50pct', 'dcir_80pct']:
        if col in df_day.columns:
            dcir_vals = df_day[col].dropna()
            if len(dcir_vals) > 0:
                dcir_values.extend(dcir_vals.tolist())
    
    avg_dcir = float(np.mean(dcir_values)) if dcir_values else None
    
    # Residual statistics (EKF prediction accuracy)
    residual_stats = {
        'residual_mean': float(df_day['residual'].mean()),
        'residual_std': float(df_day['residual'].std()),
        'residual_min': float(df_day['residual'].min()),
        'residual_max': float(df_day['residual'].max())
    }
    
    # Confidence statistics
    if 'confidence' in df_day.columns:
        confidence_avg = float(df_day['confidence'].mean())
    else:
        confidence_avg = 1.0
    
    # Build summary
    summary = {
        'vehicle_id': vehicle_id,
        'date': date,
        'energy_in_wh': energy['energy_in_wh'],
        'energy_out_wh': energy['energy_out_wh'],
        'charge_efficiency': charge_efficiency,
        'avg_temp_c': temp_stats['avg_temp_c'],
        'max_temp_c': temp_stats['max_temp_c'],
        'min_temp_c': temp_stats['min_temp_c'],
        'fast_charge_sessions': fast_charge_sessions,
        'idle_at_100pct_hours': idle_at_100pct_hours,
        'min_soc': soc_stats['min_soc'],
        'mean_soc': soc_stats['mean_soc'],
        'median_soc': soc_stats['median_soc'],
        'max_soc': soc_stats['max_soc'],
        'soh_pct': soh_pct,
        'avg_dcir': avg_dcir,
        'residual_mean': residual_stats['residual_mean'],
        'residual_std': residual_stats['residual_std'],
        'confidence_avg': confidence_avg,
        'row_count': len(df_day)
    }
    
    return summary


def generate_daily_summaries(
    ekf_dir: Path,
    output_dir: Path,
    vehicle_ids: Optional[list] = None
):
    """
    Generate daily summaries from EKF timeseries data.
    
    Args:
        ekf_dir: Directory with EKF timeseries Parquet files
        output_dir: Output directory for daily summaries
        vehicle_ids: Optional list of vehicle IDs to process
    """
    print("=" * 70)
    print("Phase 4: Daily Summaries Generation")
    print("=" * 70)
    print(f"\nInput:  {ekf_dir}")
    print(f"Output: {output_dir / 'daily_summaries'}\n")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Connect to DuckDB
    conn = duckdb.connect()
    
    # Get vehicle list
    if vehicle_ids is None:
        vehicles_query = f"""
        SELECT DISTINCT vehicle_id 
        FROM read_parquet('{ekf_dir}/**/*.parquet')
        ORDER BY vehicle_id
        """
        vehicles = conn.execute(vehicles_query).df()['vehicle_id'].tolist()
    else:
        vehicles = vehicle_ids
    
    print(f"Processing {len(vehicles)} vehicle(s)...\n")
    
    all_summaries = []
    
    # Process each vehicle
    for vehicle_id in tqdm(vehicles, unit='vehicle'):
        # Get all data for this vehicle
        vehicle_query = f"""
        SELECT *
        FROM read_parquet('{ekf_dir}/**/*.parquet')
        WHERE vehicle_id = {vehicle_id}
        ORDER BY date, time_s
        """
        
        df_vehicle = conn.execute(vehicle_query).df()
        
        if len(df_vehicle) == 0:
            continue
        
        # Ensure date is date type
        if 'date' in df_vehicle.columns:
            df_vehicle['date'] = pd.to_datetime(df_vehicle['date']).dt.date
        else:
            # Derive date if missing
            base_date = pd.to_datetime('2020-01-01')
            df_vehicle['date'] = base_date + pd.to_timedelta(
                (df_vehicle['vehicle_id'] * 50 + df_vehicle['cycle_idx']) % 10000,
                unit='D'
            )
            df_vehicle['date'] = df_vehicle['date'].dt.date
        
        # Group by date and aggregate
        dates = df_vehicle['date'].unique()
        
        for date in dates:
            df_day = df_vehicle[df_vehicle['date'] == date].copy()
            
            summary = aggregate_daily_summary(
                vehicle_id=vehicle_id,
                date=str(date),
                df_day=df_day
            )
            
            if summary:
                all_summaries.append(summary)
    
    conn.close()
    
    if not all_summaries:
        print("❌ No summaries generated")
        return
    
    # Convert to DataFrame
    df_summaries = pd.DataFrame(all_summaries)
    
    # Write to Parquet (partitioned by vehicle_id)
    output_summaries = output_dir / 'daily_summaries'
    table = pa.Table.from_pandas(df_summaries, preserve_index=False)
    pq.write_to_dataset(
        table,
        root_path=output_summaries,
        partition_cols=['vehicle_id'],
        compression='snappy',
        use_dictionary=True,
        write_statistics=True
    )
    
    # Print summary
    print("\n" + "=" * 70)
    print("Daily Summaries Summary")
    print("=" * 70)
    print(f"\nTotal summaries: {len(df_summaries):,}")
    print(f"Unique vehicles: {df_summaries['vehicle_id'].nunique()}")
    print(f"Date range: {df_summaries['date'].min()} to {df_summaries['date'].max()}")
    print(f"\nOutput: {output_summaries}")
    
    # Sample statistics
    print(f"\nSample Statistics:")
    print(f"  Avg energy out: {df_summaries['energy_out_wh'].mean():.1f} Wh")
    print(f"  Avg charge efficiency: {df_summaries['charge_efficiency'].mean():.3f}")
    print(f"  Avg SOH: {df_summaries['soh_pct'].mean():.3f}")
    print(f"  Avg temperature: {df_summaries['avg_temp_c'].mean():.1f}°C")
    
    # Save metadata
    metadata = {
        'generated_at': datetime.now().isoformat(),
        'source_dir': str(ekf_dir),
        'total_summaries': int(len(df_summaries)),
        'vehicles': [int(v) for v in df_summaries['vehicle_id'].unique()],
        'date_range': {
            'start': str(df_summaries['date'].min()),
            'end': str(df_summaries['date'].max())
        }
    }
    
    metadata_path = output_dir / 'daily_summaries_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\nMetadata: {metadata_path}")
    print("\n✅ Phase 4 Complete: Daily Summaries Generated")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate Daily Summaries (Phase 4)')
    parser.add_argument('--ekf-dir',
                       default='data/ekf_output/ekf_timeseries',
                       help='Input EKF timeseries directory')
    parser.add_argument('--output-dir',
                       default='data/daily_summaries',
                       help='Output directory for daily summaries')
    parser.add_argument('--vehicles',
                       type=int,
                       nargs='+',
                       default=None,
                       help='Specific vehicle IDs to process (default: all)')
    
    args = parser.parse_args()
    
    ekf_dir = Path(args.ekf_dir)
    output_dir = Path(args.output_dir)
    
    if not ekf_dir.exists():
        print(f"❌ Error: EKF directory not found: {ekf_dir}")
        sys.exit(1)
    
    generate_daily_summaries(
        ekf_dir=ekf_dir,
        output_dir=output_dir,
        vehicle_ids=args.vehicles
    )


if __name__ == '__main__':
    main()

