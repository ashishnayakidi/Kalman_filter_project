"""
Phase 3: Batch EKF Processing

Processes Parquet timeseries data through EKF and generates:
- SOC estimates
- SOH estimates  
- DCIR values
- Voltage predictions and residuals
- Confidence metrics

Outputs to partitioned Parquet: ekf_timeseries/vehicle_id={id}/date={date}/
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
import sys
from tqdm import tqdm
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.ekf import BatteryEKF
from agent.ocv import derive_ocv_table, ocv_lookup
from agent.scoring import get_scorer, score_tick
import os
from dotenv import load_dotenv

load_dotenv()


def derive_dcir(ekf: BatteryEKF, soc: float) -> float:
    """
    Derive DCIR (DC Internal Resistance) at given SOC.
    
    DCIR ≈ R0 + R1 (simplified, actual depends on SOC)
    """
    # Simplified: DCIR = R0 + R1
    # In practice, DCIR varies with SOC, but this is a reasonable approximation
    return ekf.R0 + ekf.R1


def process_vehicle_ekf(
    vehicle_id: int,
    df: pd.DataFrame,
    ocv_table: Optional[pd.DataFrame],
    output_dir: Path
) -> Dict:
    """
    Process a single vehicle through EKF.
    
    Args:
        vehicle_id: Vehicle ID
        df: DataFrame with timeseries data for this vehicle
        ocv_table: OCV lookup table
        output_dir: Output directory for EKF results
    
    Returns:
        Dictionary with processing statistics
    """
    # Sort by cycle and time
    df = df.sort_values(['cycle_idx', 'time_s']).copy()
    
    # Initialize EKF
    Q_Ah = float(os.getenv('Q_AH_INIT', '2.0'))
    R0 = float(os.getenv('R0_INIT', '0.03'))
    R1 = float(os.getenv('R1_INIT', '0.01'))
    C1 = float(os.getenv('C1_INIT', '2000.0'))
    eta = float(os.getenv('ETA_INIT', '0.98'))
    soc_init = float(os.getenv('SOC_INIT', '1.0'))
    Q_soc = float(os.getenv('EKF_Q_SOC', '1e-7'))
    Q_vrc = float(os.getenv('EKF_Q_VRC', '1e-5'))
    R_volt = float(os.getenv('EKF_R_VOLT', '2.5e-5'))
    
    ekf = BatteryEKF(
        Q_Ah=Q_Ah, R0=R0, R1=R1, C1=C1, eta=eta,
        soc_init=soc_init,
        Q_soc=Q_soc, Q_vrc=Q_vrc, R_volt=R_volt,
        ocv_table=ocv_table
    )
    
    # Initialize scorer
    scorer = get_scorer()
    
    # Process each row
    results = []
    last_cycle = -1
    
    for idx, row in df.iterrows():
        # Check if new cycle (reset EKF if needed)
        if row['cycle_idx'] != last_cycle:
            # Optionally reset EKF for new cycle (or continue state)
            # For now, we'll continue state across cycles
            last_cycle = row['cycle_idx']
        
        # EKF step
        try:
            ekf_out = ekf.step(
                I_A=row['current_A'],
                V_V=row['voltage_V'],
                T_C=row['temp_C'],
                dt_s=row['dt_s']
            )
            
            # Add metadata
            ekf_out['vehicle_id'] = vehicle_id
            ekf_out['cycle_idx'] = row['cycle_idx']
            ekf_out['cycle_type'] = row.get('cycle_type', 'discharge')
            ekf_out['time_s'] = row['time_s']
            ekf_out['I_A'] = row['current_A']
            ekf_out['V_V'] = row['voltage_V']
            ekf_out['T_C'] = row['temp_C']
            
            # Extract covariance
            if 'cov' in ekf_out and isinstance(ekf_out['cov'], list):
                cov = np.array(ekf_out['cov'])
                ekf_out['cov_soc'] = float(cov[0, 0])
                ekf_out['cov_vrc'] = float(cov[1, 1])
            else:
                ekf_out['cov_soc'] = 0.0
                ekf_out['cov_vrc'] = 0.0
            
            # Calculate confidence (inverse of normalized covariance)
            # Higher covariance = lower confidence
            max_cov_soc = 0.1  # Normalization factor
            confidence = max(0.0, min(1.0, 1.0 - (ekf_out['cov_soc'] / max_cov_soc)))
            ekf_out['confidence'] = confidence
            
            # Calculate DCIR at different SOC levels
            soc = ekf_out['soc']
            if soc <= 0.1:
                ekf_out['dcir_10pct'] = derive_dcir(ekf, 0.1)
            else:
                ekf_out['dcir_10pct'] = None
            
            if 0.45 <= soc <= 0.55:
                ekf_out['dcir_50pct'] = derive_dcir(ekf, 0.5)
            else:
                ekf_out['dcir_50pct'] = None
            
            if soc >= 0.8:
                ekf_out['dcir_80pct'] = derive_dcir(ekf, 0.8)
            else:
                ekf_out['dcir_80pct'] = None
            
            # Current capacity estimate (Q_now)
            # This is the effective capacity based on SOC tracking
            # Simplified: Q_now = Q_Ah (can be refined based on SOC changes)
            ekf_out['Q_now'] = Q_Ah
            
            # SOH estimate (State of Health)
            # SOH = Q_now / Q_nominal (simplified)
            Q_nominal = Q_Ah  # Nominal capacity
            ekf_out['soh_pct'] = min(1.0, max(0.0, ekf_out['Q_now'] / Q_nominal))
            
            # Score the tick
            score_tick(ekf_out)
            
            results.append(ekf_out)
            
        except Exception as e:
            print(f"  ⚠️  Error processing row {idx}: {e}")
            continue
    
    # Convert to DataFrame
    if not results:
        return {'vehicle_id': vehicle_id, 'rows_processed': 0, 'error': 'No results'}
    
    df_results = pd.DataFrame(results)
    
    # Add date column if not present
    if 'date' not in df_results.columns and 'date' in df.columns:
        # Merge date from original df
        df_results = df_results.merge(
            df[['cycle_idx', 'time_s', 'date']].drop_duplicates(),
            on=['cycle_idx', 'time_s'],
            how='left'
        )
    
    if 'date' not in df_results.columns:
        # Derive date
        base_date = pd.to_datetime('2020-01-01')
        df_results['date'] = ((df_results['vehicle_id'] * 50 + df_results['cycle_idx']) % 10000).astype('int32')
        df_results['date'] = base_date + pd.to_timedelta(df_results['date'], unit='D')
        df_results['date'] = df_results['date'].dt.date
    
    # Write to Parquet
    output_timeseries = output_dir / 'ekf_timeseries'
    table = pa.Table.from_pandas(df_results, preserve_index=False)
    pq.write_to_dataset(
        table,
        root_path=output_timeseries,
        partition_cols=['vehicle_id', 'date'],
        compression='snappy',
        use_dictionary=True,
        write_statistics=True
    )
    
    # Get daily summary from scorer
    daily_summary = scorer.daily_summary()
    
    return {
        'vehicle_id': vehicle_id,
        'rows_processed': len(results),
        'unique_cycles': int(df_results['cycle_idx'].nunique()),
        'soc_range': (float(df_results['soc'].min()), float(df_results['soc'].max())),
        'soh_range': (float(df_results['soh_pct'].min()), float(df_results['soh_pct'].max())),
        'residual_mean': float(df_results['residual'].mean()),
        'residual_std': float(df_results['residual'].std()),
        'confidence_avg': float(df_results['confidence'].mean())
    }


def batch_ekf_processing(
    parquet_dir: Path,
    output_dir: Path,
    vehicle_ids: Optional[List[int]] = None
):
    """
    Process all vehicles through EKF.
    
    Args:
        parquet_dir: Input Parquet directory (timeseries data)
        output_dir: Output directory for EKF results
        vehicle_ids: Optional list of vehicle IDs to process (None = all)
    """
    print("=" * 70)
    print("Phase 3: Batch EKF Processing")
    print("=" * 70)
    print(f"\nInput:  {parquet_dir / 'timeseries'}")
    print(f"Output: {output_dir / 'ekf_timeseries'}\n")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Connect to DuckDB
    conn = duckdb.connect()
    
    # Get vehicle list
    if vehicle_ids is None:
        vehicles_query = f"""
        SELECT DISTINCT vehicle_id 
        FROM read_parquet('{parquet_dir}/timeseries/**/*.parquet')
        ORDER BY vehicle_id
        """
        vehicles = conn.execute(vehicles_query).df()['vehicle_id'].tolist()
    else:
        vehicles = vehicle_ids
    
    print(f"Processing {len(vehicles)} vehicle(s)...\n")
    
    # Derive OCV table from all data (or sample)
    print("Deriving OCV table...")
    ocv_query = f"""
    SELECT voltage_V, current_A, temp_C
    FROM read_parquet('{parquet_dir}/timeseries/**/*.parquet')
    WHERE ABS(current_A) < 0.05
    LIMIT 10000
    """
    df_ocv_sample = conn.execute(ocv_query).df()
    
    if len(df_ocv_sample) > 0:
        # Add dummy SOC for OCV derivation (will be estimated)
        df_ocv_sample['soc'] = np.linspace(1.0, 0.0, len(df_ocv_sample))
        ocv_table = derive_ocv_table(df_ocv_sample)
        print(f"  ✅ Derived OCV table with {len(ocv_table)} points")
    else:
        print("  ⚠️  Could not derive OCV table, using fallback")
        ocv_table = None
    
    # Process each vehicle
    stats = []
    total_rows = 0
    
    with tqdm(total=len(vehicles), unit='vehicle') as pbar:
        for vehicle_id in vehicles:
            # Read vehicle data
            vehicle_query = f"""
            SELECT *
            FROM read_parquet('{parquet_dir}/timeseries/**/*.parquet')
            WHERE vehicle_id = {vehicle_id}
            ORDER BY cycle_idx, time_s
            """
            
            df_vehicle = conn.execute(vehicle_query).df()
            
            if len(df_vehicle) == 0:
                print(f"  ⚠️  No data for vehicle {vehicle_id}")
                pbar.update(1)
                continue
            
            # Process through EKF
            vehicle_stats = process_vehicle_ekf(
                vehicle_id=vehicle_id,
                df=df_vehicle,
                ocv_table=ocv_table,
                output_dir=output_dir
            )
            
            stats.append(vehicle_stats)
            total_rows += vehicle_stats['rows_processed']
            pbar.update(1)
            
            if vehicle_stats['rows_processed'] > 0:
                print(f"  ✅ Vehicle {vehicle_id}: {vehicle_stats['rows_processed']:,} rows, "
                      f"SOC: {vehicle_stats['soc_range'][0]:.3f}-{vehicle_stats['soc_range'][1]:.3f}, "
                      f"SOH: {vehicle_stats['soh_range'][0]:.3f}-{vehicle_stats['soh_range'][1]:.3f}")
    
    conn.close()
    
    # Generate summary
    print("\n" + "=" * 70)
    print("EKF Processing Summary")
    print("=" * 70)
    print(f"\nTotal vehicles processed: {len([s for s in stats if s['rows_processed'] > 0])}")
    print(f"Total rows processed: {total_rows:,}")
    print(f"\nOutput: {output_dir / 'ekf_timeseries'}")
    
    # Save processing metadata
    metadata = {
        'processing_date': datetime.now().isoformat(),
        'input_dir': str(parquet_dir),
        'vehicles_processed': vehicles,
        'statistics': stats,
        'total_rows': total_rows
    }
    
    metadata_path = output_dir / 'ekf_processing_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Metadata: {metadata_path}")
    print("\n✅ Phase 3 Complete: EKF Processing")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch EKF Processing (Phase 3)')
    parser.add_argument('--parquet-dir',
                       default='data/parquet_dev',
                       help='Input Parquet directory (default: data/parquet_dev)')
    parser.add_argument('--output-dir',
                       default='data/ekf_output',
                       help='Output directory for EKF results')
    parser.add_argument('--vehicles',
                       type=int,
                       nargs='+',
                       default=None,
                       help='Specific vehicle IDs to process (default: all)')
    
    args = parser.parse_args()
    
    parquet_dir = Path(args.parquet_dir)
    output_dir = Path(args.output_dir)
    
    if not (parquet_dir / 'timeseries').exists():
        print(f"❌ Error: Parquet directory not found: {parquet_dir / 'timeseries'}")
        sys.exit(1)
    
    batch_ekf_processing(
        parquet_dir=parquet_dir,
        output_dir=output_dir,
        vehicle_ids=args.vehicles
    )


if __name__ == '__main__':
    main()

