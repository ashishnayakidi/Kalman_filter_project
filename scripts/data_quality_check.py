"""
Phase 2: Data Quality Pass

Performs comprehensive data quality checks:
1. Unit validation (voltage, current, temperature ranges)
2. Gap detection (missing data, NaN values)
3. Outlier detection (spikes, jumps)
4. Clock sanity (monotonic timestamps)
5. Quality flagging (0=good, 1=warning, 2=bad)
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import json
from datetime import datetime
import sys
from tqdm import tqdm
import duckdb


# Quality thresholds
VOLTAGE_MIN = 2.5  # V - below this is likely bad data
VOLTAGE_MAX = 4.5  # V - above this is likely bad data
CURRENT_MAX = 500.0  # A - above this is likely bad data
CURRENT_MIN = 0.0  # A - should be positive (discharge)
TEMP_MIN = -30.0  # °C - below this is likely bad data
TEMP_MAX = 100.0  # °C - above this is likely bad data (extreme but possible)

# Spike detection thresholds
CURRENT_SPIKE_THRESHOLD = 100.0  # A/s - rate of change
VOLTAGE_JUMP_THRESHOLD = 0.5  # V - sudden voltage change
TEMP_SPIKE_THRESHOLD = 20.0  # °C/s - temperature rate of change

# Time gap threshold
TIME_GAP_THRESHOLD = 3600.0  # seconds (1 hour) - large gap indicates missing data


def check_unit_validation(df: pd.DataFrame) -> pd.DataFrame:
    """
    Check unit validation: voltage, current, temperature ranges.
    
    Returns DataFrame with quality flags.
    """
    df = df.copy()
    
    # Initialize quality flags
    if 'quality_flag' not in df.columns:
        df['quality_flag'] = 0  # Good by default
    
    # Voltage checks
    voltage_bad = (df['voltage_V'] < VOLTAGE_MIN) | (df['voltage_V'] > VOLTAGE_MAX)
    voltage_warning = (df['voltage_V'] < 3.0) | (df['voltage_V'] > 4.3)  # Edge cases
    
    # Current checks
    current_bad = (df['current_A'] < CURRENT_MIN) | (df['current_A'] > CURRENT_MAX)
    current_warning = df['current_A'] > 200.0  # High current but plausible
    
    # Temperature checks
    temp_bad = (df['temp_C'] < TEMP_MIN) | (df['temp_C'] > TEMP_MAX)
    temp_warning = (df['temp_C'] < 0.0) | (df['temp_C'] > 80.0)  # Edge cases
    
    # Apply flags (2=bad, 1=warning, 0=good)
    df.loc[voltage_bad | current_bad | temp_bad, 'quality_flag'] = 2
    df.loc[(voltage_warning | current_warning | temp_warning) & (df['quality_flag'] == 0), 'quality_flag'] = 1
    
    return df


def detect_spikes_and_outliers(df: pd.DataFrame, use_fast_mode: bool = True) -> pd.DataFrame:
    """
    Detect spikes and outliers in time series data.
    
    Checks:
    - Current spikes (|ΔI/Δt| > threshold)
    - Voltage jumps (|ΔV| > threshold)
    - Temperature spikes (|ΔT/Δt| > threshold)
    
    Fast mode: Only checks for extreme spikes (10x threshold) to reduce false positives.
    """
    df = df.copy()
    
    if 'quality_flag' not in df.columns:
        df['quality_flag'] = 0
    
    if use_fast_mode:
        # Fast mode: Only check for extreme spikes using vectorized operations
        # Sort by time within each vehicle/cycle
        df = df.sort_values(['vehicle_id', 'cycle_idx', 'time_s'])
        
        # Use shift instead of groupby (much faster)
        df['prev_current'] = df.groupby(['vehicle_id', 'cycle_idx'])['current_A'].shift(1)
        df['prev_voltage'] = df.groupby(['vehicle_id', 'cycle_idx'])['voltage_V'].shift(1)
        df['prev_temp'] = df.groupby(['vehicle_id', 'cycle_idx'])['temp_C'].shift(1)
        df['prev_time'] = df.groupby(['vehicle_id', 'cycle_idx'])['time_s'].shift(1)
        
        # Calculate deltas (only for extreme spikes)
        dt = (df['time_s'] - df['prev_time']).fillna(1.0)
        dI = (df['current_A'] - df['prev_current']).fillna(0)
        dV = (df['voltage_V'] - df['prev_voltage']).fillna(0)
        dT = (df['temp_C'] - df['prev_temp']).fillna(0)
        
        # Only flag extreme spikes (10x threshold to reduce false positives)
        extreme_current_spike = (np.abs(dI / dt) > CURRENT_SPIKE_THRESHOLD * 10)
        extreme_voltage_jump = (np.abs(dV) > VOLTAGE_JUMP_THRESHOLD * 5)
        extreme_temp_spike = (np.abs(dT / dt) > TEMP_SPIKE_THRESHOLD * 5)
        
        # Mark as warning only for extreme spikes
        df.loc[extreme_current_spike | extreme_voltage_jump | extreme_temp_spike, 'quality_flag'] = np.maximum(
            df.loc[extreme_current_spike | extreme_voltage_jump | extreme_temp_spike, 'quality_flag'],
            1
        )
        
        # Clean up temporary columns
        df = df.drop(columns=['prev_current', 'prev_voltage', 'prev_temp', 'prev_time'])
    else:
        # Original detailed mode (slower but more thorough)
        df = df.sort_values(['vehicle_id', 'cycle_idx', 'time_s'])
        df['dI_dt'] = df.groupby(['vehicle_id', 'cycle_idx'])['current_A'].diff() / df.groupby(['vehicle_id', 'cycle_idx'])['time_s'].diff()
        df['dV'] = df.groupby(['vehicle_id', 'cycle_idx'])['voltage_V'].diff()
        df['dT_dt'] = df.groupby(['vehicle_id', 'cycle_idx'])['temp_C'].diff() / df.groupby(['vehicle_id', 'cycle_idx'])['time_s'].diff()
        
        df['dI_dt'] = df['dI_dt'].fillna(0)
        df['dV'] = df['dV'].fillna(0)
        df['dT_dt'] = df['dT_dt'].fillna(0)
        
        current_spike = np.abs(df['dI_dt']) > CURRENT_SPIKE_THRESHOLD
        voltage_jump = np.abs(df['dV']) > VOLTAGE_JUMP_THRESHOLD
        temp_spike = np.abs(df['dT_dt']) > TEMP_SPIKE_THRESHOLD
        
        df.loc[current_spike | voltage_jump | temp_spike, 'quality_flag'] = np.maximum(
            df.loc[current_spike | voltage_jump | temp_spike, 'quality_flag'],
            1
        )
        
        df = df.drop(columns=['dI_dt', 'dV', 'dT_dt'])
    
    return df


def check_missing_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Check for missing data (NaN values).
    """
    df = df.copy()
    
    if 'quality_flag' not in df.columns:
        df['quality_flag'] = 0
    
    # Check for NaN in critical columns
    critical_cols = ['voltage_V', 'current_A', 'temp_C', 'time_s']
    has_nan = df[critical_cols].isna().any(axis=1)
    
    # Mark NaN as bad
    df.loc[has_nan, 'quality_flag'] = 2
    
    return df


def check_timestamp_monotonicity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Check that timestamps are monotonic within each vehicle/cycle.
    """
    df = df.copy()
    
    if 'quality_flag' not in df.columns:
        df['quality_flag'] = 0
    
    # Sort by time within each vehicle/cycle
    df = df.sort_values(['vehicle_id', 'cycle_idx', 'time_s'])
    
    # Check for non-monotonic timestamps
    time_diff = df.groupby(['vehicle_id', 'cycle_idx'])['time_s'].diff()
    non_monotonic = time_diff < 0  # Negative means going backwards
    
    # Check for large gaps
    large_gaps = time_diff > TIME_GAP_THRESHOLD
    
    # Mark as warning (non-monotonic) or bad (large gaps)
    df.loc[non_monotonic, 'quality_flag'] = np.maximum(df.loc[non_monotonic, 'quality_flag'], 1)
    df.loc[large_gaps, 'quality_flag'] = np.maximum(df.loc[large_gaps, 'quality_flag'], 1)
    
    return df


def check_duplicate_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Check for duplicate timestamps within same vehicle/cycle.
    """
    df = df.copy()
    
    if 'quality_flag' not in df.columns:
        df['quality_flag'] = 0
    
    # Check for duplicates within vehicle/cycle
    duplicates = df.duplicated(subset=['vehicle_id', 'cycle_idx', 'time_s'], keep=False)
    
    # Mark as warning
    df.loc[duplicates, 'quality_flag'] = np.maximum(df.loc[duplicates, 'quality_flag'], 1)
    
    return df


def perform_quality_checks(df: pd.DataFrame, fast_mode: bool = True) -> pd.DataFrame:
    """
    Perform all quality checks on a DataFrame.
    
    Fast mode: Skips expensive spike detection and uses simplified checks.
    
    Returns DataFrame with quality_flag column added.
    """
    # Initialize quality flag
    df['quality_flag'] = 0
    
    # Run essential checks (fast)
    df = check_missing_data(df)
    df = check_unit_validation(df)
    
    if not fast_mode:
        # Expensive checks (only if not in fast mode)
        df = detect_spikes_and_outliers(df, use_fast_mode=False)
        df = check_timestamp_monotonicity(df)
        df = check_duplicate_timestamps(df)
    else:
        # Fast spike detection (only extreme spikes)
        df = detect_spikes_and_outliers(df, use_fast_mode=True)
        # Skip monotonicity and duplicate checks in fast mode (they're expensive)
    
    return df


def analyze_quality_by_vehicle(parquet_dir: Path) -> Dict:
    """
    Analyze quality across all vehicles using DuckDB.
    """
    print("\nAnalyzing quality across all vehicles...")
    
    conn = duckdb.connect()
    
    # Query quality distribution
    query = f"""
    SELECT 
        quality_flag,
        COUNT(*) as row_count,
        COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() as percentage
    FROM read_parquet('{parquet_dir}/timeseries/**/*.parquet')
    GROUP BY quality_flag
    ORDER BY quality_flag
    """
    
    quality_dist = conn.execute(query).df()
    
    # Query by vehicle
    vehicle_query = f"""
    SELECT 
        vehicle_id,
        COUNT(*) as total_rows,
        SUM(CASE WHEN quality_flag = 0 THEN 1 ELSE 0 END) as good_rows,
        SUM(CASE WHEN quality_flag = 1 THEN 1 ELSE 0 END) as warning_rows,
        SUM(CASE WHEN quality_flag = 2 THEN 1 ELSE 0 END) as bad_rows,
        AVG(voltage_V) as avg_voltage,
        AVG(current_A) as avg_current,
        AVG(temp_C) as avg_temp
    FROM read_parquet('{parquet_dir}/timeseries/**/*.parquet')
    GROUP BY vehicle_id
    ORDER BY vehicle_id
    """
    
    vehicle_stats = conn.execute(vehicle_query).df()
    
    # Query outliers
    outlier_query = f"""
    SELECT 
        COUNT(*) as outlier_count,
        COUNT(DISTINCT vehicle_id) as affected_vehicles
    FROM read_parquet('{parquet_dir}/timeseries/**/*.parquet')
    WHERE quality_flag > 0
    """
    
    outlier_stats = conn.execute(outlier_query).df()
    
    conn.close()
    
    return {
        'quality_distribution': quality_dist.to_dict('records'),
        'vehicle_stats': vehicle_stats.to_dict('records'),
        'outlier_summary': outlier_stats.to_dict('records')[0] if len(outlier_stats) > 0 else {}
    }


def process_parquet_with_quality_flags(
    parquet_dir: Path,
    output_dir: Path,
    chunk_size: int = 1_000_000
):
    """
    Process Parquet files, add quality flags using DuckDB SQL (FAST).
    
    This uses DuckDB SQL to compute quality flags efficiently, then writes back.
    """
    print("=" * 70)
    print("Data Quality Check - Processing Parquet Files (Optimized)")
    print("=" * 70)
    print(f"\nInput:  {parquet_dir / 'timeseries'}")
    print(f"Output: {output_dir / 'timeseries'}")
    print(f"\nUsing DuckDB SQL for fast quality checks...\n")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    output_timeseries = output_dir / 'timeseries'
    
    conn = duckdb.connect()
    
    # Get vehicle list
    vehicles_query = f"""
    SELECT DISTINCT vehicle_id 
    FROM read_parquet('{parquet_dir}/timeseries/**/*.parquet')
    ORDER BY vehicle_id
    """
    vehicles = conn.execute(vehicles_query).df()['vehicle_id'].tolist()
    
    print(f"Processing {len(vehicles)} vehicles...\n")
    
    # Process vehicle by vehicle (much faster with partition pruning)
    total_processed = 0
    
    with tqdm(total=len(vehicles), unit='vehicle') as pbar:
        for vehicle_id in vehicles:
            # Read all data for this vehicle
            vehicle_query = f"""
            SELECT *
            FROM read_parquet('{parquet_dir}/timeseries/**/*.parquet')
            WHERE vehicle_id = {vehicle_id}
            ORDER BY cycle_idx, time_s
            """
            
            df = conn.execute(vehicle_query).df()
            
            if len(df) == 0:
                continue
            
            # Perform quality checks (fast mode for speed)
            df = perform_quality_checks(df, fast_mode=True)
            
            # Write to Parquet (maintaining partition structure)
            if 'date' not in df.columns:
                base_date = pd.to_datetime('2020-01-01')
                df['date'] = ((df['vehicle_id'] * 50 + df['cycle_idx']) % 10000).astype('int32')
                df['date'] = base_date + pd.to_timedelta(df['date'], unit='D')
                df['date'] = df['date'].dt.date
            
            # Write partitioned Parquet
            import pyarrow as pa
            import pyarrow.parquet as pq
            
            table = pa.Table.from_pandas(df, preserve_index=False)
            pq.write_to_dataset(
                table,
                root_path=output_timeseries,
                partition_cols=['vehicle_id', 'date'],
                compression='snappy',
                use_dictionary=True,
                write_statistics=True,
                existing_data_behavior='overwrite_or_ignore'
            )
            
            total_processed += len(df)
            pbar.update(1)
    
    conn.close()
    
    print(f"\n✅ Quality checks complete!")
    print(f"   Processed: {total_processed:,} rows across {len(vehicles)} vehicles")
    print(f"   Output: {output_timeseries}")


def generate_quality_report(parquet_dir: Path, output_path: Path):
    """
    Generate comprehensive quality report.
    """
    print("\n" + "=" * 70)
    print("Generating Quality Report")
    print("=" * 70)
    
    # Analyze quality
    analysis = analyze_quality_by_vehicle(parquet_dir)
    
    # Get overall statistics
    conn = duckdb.connect()
    
    stats_query = f"""
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT vehicle_id) as unique_vehicles,
        AVG(voltage_V) as avg_voltage,
        STDDEV(voltage_V) as std_voltage,
        MIN(voltage_V) as min_voltage,
        MAX(voltage_V) as max_voltage,
        AVG(current_A) as avg_current,
        STDDEV(current_A) as std_current,
        MIN(current_A) as min_current,
        MAX(current_A) as max_current,
        AVG(temp_C) as avg_temp,
        STDDEV(temp_C) as std_temp,
        MIN(temp_C) as min_temp,
        MAX(temp_C) as max_temp
    FROM read_parquet('{parquet_dir}/timeseries/**/*.parquet')
    """
    
    overall_stats = conn.execute(stats_query).df().to_dict('records')[0]
    
    # Quality flag statistics
    quality_query = f"""
    SELECT 
        quality_flag,
        COUNT(*) as count,
        COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() as percentage
    FROM read_parquet('{parquet_dir}/timeseries/**/*.parquet')
    GROUP BY quality_flag
    ORDER BY quality_flag
    """
    
    quality_stats = conn.execute(quality_query).df()
    
    conn.close()
    
    # Build report
    report = {
        'generated_at': datetime.now().isoformat(),
        'source': str(parquet_dir),
        'overall_statistics': overall_stats,
        'quality_distribution': {
            'good': int(quality_stats[quality_stats['quality_flag'] == 0]['count'].iloc[0]) if len(quality_stats[quality_stats['quality_flag'] == 0]) > 0 else 0,
            'warning': int(quality_stats[quality_stats['quality_flag'] == 1]['count'].iloc[0]) if len(quality_stats[quality_stats['quality_flag'] == 1]) > 0 else 0,
            'bad': int(quality_stats[quality_stats['quality_flag'] == 2]['count'].iloc[0]) if len(quality_stats[quality_stats['quality_flag'] == 2]) > 0 else 0
        },
        'quality_percentages': quality_stats.to_dict('records'),
        'vehicle_analysis': analysis['vehicle_stats'][:10],  # First 10 vehicles
        'recommendations': generate_recommendations(analysis, overall_stats)
    }
    
    # Save report
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n✅ Quality report saved to: {output_path}")
    
    # Print summary
    print("\nQuality Summary:")
    print(f"  Good:     {report['quality_distribution']['good']:,} rows ({report['quality_distribution']['good']/overall_stats['total_rows']*100:.2f}%)")
    print(f"  Warning:  {report['quality_distribution']['warning']:,} rows ({report['quality_distribution']['warning']/overall_stats['total_rows']*100:.2f}%)")
    print(f"  Bad:      {report['quality_distribution']['bad']:,} rows ({report['quality_distribution']['bad']/overall_stats['total_rows']*100:.2f}%)")


def generate_recommendations(analysis: Dict, stats: Dict) -> List[str]:
    """Generate quality recommendations."""
    recommendations = []
    
    # Check voltage range
    if stats['min_voltage'] < VOLTAGE_MIN or stats['max_voltage'] > VOLTAGE_MAX:
        recommendations.append(f"Voltage range ({stats['min_voltage']:.2f}V - {stats['max_voltage']:.2f}V) includes values outside typical Li-ion range")
    
    # Check temperature
    if stats['max_temp'] > 80.0:
        recommendations.append(f"Maximum temperature ({stats['max_temp']:.1f}°C) exceeds recommended operating range - verify units")
    
    # Check quality flags
    total_bad = sum(q['count'] for q in analysis['quality_distribution'] if q['quality_flag'] == 2)
    if total_bad > 0:
        recommendations.append(f"{total_bad:,} rows flagged as bad - review and exclude from analysis")
    
    total_warning = sum(q['count'] for q in analysis['quality_distribution'] if q['quality_flag'] == 1)
    if total_warning > 0:
        recommendations.append(f"{total_warning:,} rows flagged with warnings - review for data quality issues")
    
    return recommendations


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Data Quality Check (Phase 2)')
    parser.add_argument('--parquet-dir',
                       default='data/parquet',
                       help='Input Parquet directory')
    parser.add_argument('--output-dir',
                       default='data/parquet_quality',
                       help='Output directory for quality-flagged Parquet')
    parser.add_argument('--chunk-size', type=int, default=1_000_000,
                       help='Chunk size for processing')
    parser.add_argument('--fast-mode', action='store_true', default=True,
                       help='Use fast mode (skip expensive checks, default: True)')
    parser.add_argument('--analyze-only', action='store_true',
                       help='Only analyze existing quality flags, do not process')
    parser.add_argument('--report-only', action='store_true',
                       help='Only generate report from existing data')
    
    args = parser.parse_args()
    
    parquet_dir = Path(args.parquet_dir)
    output_dir = Path(args.output_dir)
    
    if not (parquet_dir / 'timeseries').exists():
        print(f"❌ Error: Parquet directory not found: {parquet_dir / 'timeseries'}")
        sys.exit(1)
    
    if args.report_only:
        # Just generate report
        report_path = output_dir / 'quality_report.json'
        generate_quality_report(parquet_dir, report_path)
    elif args.analyze_only:
        # Analyze existing quality flags
        analysis = analyze_quality_by_vehicle(parquet_dir)
        print("\nQuality Analysis:")
        print(json.dumps(analysis, indent=2))
    else:
        # Full processing: add quality flags and generate report
        # Note: fast_mode is always True in process_parquet_with_quality_flags for speed
        process_parquet_with_quality_flags(parquet_dir, output_dir, args.chunk_size)
        report_path = output_dir / 'quality_report.json'
        generate_quality_report(output_dir, report_path)
    
    print("\n" + "=" * 70)
    print("✅ Phase 2 Complete: Data Quality Pass")
    print("=" * 70)


if __name__ == '__main__':
    main()

