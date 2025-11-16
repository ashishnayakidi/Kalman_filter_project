"""
Create development subset from full Parquet dataset.

Extracts selected vehicles to a smaller dev dataset for fast iteration.
"""
import duckdb
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
import sys
from datetime import datetime


def create_dev_subset(
    source_dir: Path,
    output_dir: Path,
    vehicle_ids: list,
    vehicle_name: str = "dev"
):
    """
    Create development subset with selected vehicles.
    
    Args:
        source_dir: Source Parquet directory (data/parquet)
        output_dir: Output directory (data/parquet_dev)
        vehicle_ids: List of vehicle IDs to extract
        vehicle_name: Name for the subset (for documentation)
    """
    print("=" * 70)
    print(f"Creating Development Subset: {vehicle_name}")
    print("=" * 70)
    print(f"\nSource: {source_dir / 'timeseries'}")
    print(f"Output: {output_dir / 'timeseries'}")
    print(f"Vehicles: {vehicle_ids}\n")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    output_timeseries = output_dir / 'timeseries'
    
    # Connect to DuckDB
    conn = duckdb.connect()
    
    # Get data for selected vehicles
    vehicle_list = ','.join(map(str, vehicle_ids))
    query = f"""
    SELECT *
    FROM read_parquet('{source_dir}/timeseries/**/*.parquet')
    WHERE vehicle_id IN ({vehicle_list})
    ORDER BY vehicle_id, cycle_idx, time_s
    """
    
    print("Extracting data...")
    df = conn.execute(query).df()
    
    if len(df) == 0:
        print(f"❌ Error: No data found for vehicles {vehicle_ids}")
        return False
    
    print(f"✅ Extracted {len(df):,} rows")
    print(f"   Unique vehicles: {df['vehicle_id'].nunique()}")
    print(f"   Unique cycles: {df['cycle_idx'].nunique()}")
    print(f"   Date range: {df['date'].min()} to {df['date'].max()}")
    
    # Ensure date column exists
    if 'date' not in df.columns:
        base_date = pd.to_datetime('2020-01-01')
        df['date'] = ((df['vehicle_id'] * 50 + df['cycle_idx']) % 10000).astype('int32')
        df['date'] = base_date + pd.to_timedelta(df['date'], unit='D')
        df['date'] = df['date'].dt.date
    
    # Write to Parquet (maintaining partition structure)
    print("\nWriting to Parquet...")
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_to_dataset(
        table,
        root_path=output_timeseries,
        partition_cols=['vehicle_id', 'date'],
        compression='snappy',
        use_dictionary=True,
        write_statistics=True
    )
    
    # Get final stats
    output_files = list(output_timeseries.rglob('*.parquet'))
    total_size = sum(f.stat().st_size for f in output_files)
    
    print(f"\n✅ Development subset created!")
    print(f"   Output: {output_timeseries}")
    print(f"   Files: {len(output_files)}")
    print(f"   Size: {total_size / (1024**2):.1f} MB")
    
    # Create metadata file
    metadata = {
        'subset_name': vehicle_name,
        'source': str(source_dir),
        'vehicles': vehicle_ids,
        'total_rows': len(df),
        'unique_vehicles': int(df['vehicle_id'].nunique()),
        'unique_cycles': int(df['cycle_idx'].nunique()),
        'size_mb': round(total_size / (1024**2), 2),
        'created_at': datetime.now().isoformat()
    }
    
    import json
    metadata_path = output_dir / 'subset_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"   Metadata: {metadata_path}")
    
    conn.close()
    return True


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Create development subset from Parquet data')
    parser.add_argument('--source-dir',
                       default='data/parquet',
                       help='Source Parquet directory')
    parser.add_argument('--output-dir',
                       default='data/parquet_dev',
                       help='Output directory for dev subset')
    parser.add_argument('--vehicles',
                       type=int,
                       nargs='+',
                       default=[0],
                       help='Vehicle IDs to extract (default: [0])')
    parser.add_argument('--name',
                       default='dev',
                       help='Name for the subset')
    
    args = parser.parse_args()
    
    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    
    if not (source_dir / 'timeseries').exists():
        print(f"❌ Error: Source directory not found: {source_dir / 'timeseries'}")
        sys.exit(1)
    
    success = create_dev_subset(
        source_dir=source_dir,
        output_dir=output_dir,
        vehicle_ids=args.vehicles,
        vehicle_name=args.name
    )
    
    if success:
        print("\n" + "=" * 70)
        print("✅ Development Subset Ready")
        print("=" * 70)
        print(f"\nUse this for Phase 3:")
        print(f"  python scripts/batch_ekf_processing.py --parquet-dir {output_dir}")
        print(f"\nOr query with DuckDB:")
        print(f"  SELECT * FROM read_parquet('{output_dir}/timeseries/**/*.parquet')")
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()

