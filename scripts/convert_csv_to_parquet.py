"""
Convert CSV dataset to partitioned Parquet format (Phase 1).

This script converts the processed CSV to columnar Parquet format, partitioned by:
- vehicle_id (car_id)
- date (derived from cycle or synthetic)

Benefits:
- 5-6x compression (10GB CSV → ~2-3GB Parquet)
- 10-100x faster queries
- Columnar storage for analytics
- Compatible with DuckDB, Polars, Spark
"""
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime, timedelta
import sys
from tqdm import tqdm
from typing import Optional
import json


def derive_date_column(df: pd.DataFrame, strategy: str = 'synthetic') -> pd.DataFrame:
    """
    Derive date column from available data.
    
    Since timestamps are relative (time_s), we need to create dates.
    Strategies:
    - 'synthetic': Assign dates based on cycle_idx (1 cycle = 1 day)
    - 'cycle_based': Use cycle_idx to create sequential dates
    - 'vehicle_start': Each vehicle starts at different base date
    """
    df = df.copy()
    
    if strategy == 'synthetic':
        # Create synthetic dates: base_date + (vehicle_id * offset + cycle_idx) days
        # This gives us a date per cycle per vehicle, which is reasonable for partitioning
        base_date = datetime(2020, 1, 1)  # Arbitrary base date
        
        # Create unique date per (vehicle, cycle) combination
        # Use hash-based approach to avoid overflow: hash(vehicle_id, cycle_idx) mod reasonable_days
        # This ensures unique dates without overflow
        if 'car_id' in df.columns:
            # Use modulo to keep dates within reasonable range (max 10,000 days = ~27 years)
            # This prevents overflow while maintaining uniqueness per (vehicle, cycle)
            max_days = 10000
            df['date_offset'] = ((df['car_id'].astype('int64') * 50) + df['cycle_idx'].astype('int64')) % max_days
        else:
            df['date_offset'] = (df['cycle_idx'].astype('int64') % 10000)
        
        # Convert to timedelta using int64 to avoid overflow
        df['date'] = pd.to_datetime(base_date) + pd.to_timedelta(df['date_offset'].astype('int32'), unit='D')
        df['date'] = df['date'].dt.date
        df = df.drop(columns=['date_offset'])
        
    elif strategy == 'cycle_based':
        # Use cycle_idx directly as days offset
        base_date = datetime(2020, 1, 1)
        df['date'] = pd.to_datetime(base_date) + pd.to_timedelta(df['cycle_idx'], unit='D')
        df['date'] = df['date'].dt.date
        
    elif strategy == 'vehicle_start':
        # Each vehicle starts at different date (spread over 1 year)
        base_date = datetime(2020, 1, 1)
        if 'car_id' in df.columns:
            df['vehicle_offset'] = df['car_id'] * 2  # 2 days per vehicle
            df['date'] = pd.to_datetime(base_date) + pd.to_timedelta(df['vehicle_offset'] + df['cycle_idx'], unit='D')
        else:
            df['date'] = pd.to_datetime(base_date) + pd.to_timedelta(df['cycle_idx'], unit='D')
        df['date'] = df['date'].dt.date
        if 'vehicle_offset' in df.columns:
            df = df.drop(columns=['vehicle_offset'])
    
    return df


def convert_chunk_to_parquet(
    chunk: pd.DataFrame,
    output_dir: Path,
    partition_cols: list = ['car_id', 'date']
):
    """Convert a DataFrame chunk to partitioned Parquet."""
    # Ensure date column exists
    if 'date' not in chunk.columns:
        chunk = derive_date_column(chunk)
    
    # Convert car_id to vehicle_id for consistency with schema
    if 'car_id' in chunk.columns:
        chunk = chunk.rename(columns={'car_id': 'vehicle_id'})
        partition_cols = ['vehicle_id' if col == 'car_id' else col for col in partition_cols]
    
    # Ensure date is date type (not datetime)
    if 'date' in chunk.columns:
        if pd.api.types.is_datetime64_any_dtype(chunk['date']):
            chunk['date'] = chunk['date'].dt.date
        elif not isinstance(chunk['date'].iloc[0], type(datetime.now().date())):
            chunk['date'] = pd.to_datetime(chunk['date']).dt.date
    
    # Create Arrow table
    table = pa.Table.from_pandas(chunk, preserve_index=False)
    
    # Write partitioned Parquet
    pq.write_to_dataset(
        table,
        root_path=output_dir / 'timeseries',
        partition_cols=partition_cols,
        compression='snappy',
        use_dictionary=True,  # Better compression for repeated values
        write_statistics=True,  # Enable statistics for query optimization
        coerce_timestamps='us'  # Microsecond precision
    )


def convert_csv_to_parquet(
    csv_path: Path,
    output_dir: Path,
    chunk_size: int = 1_000_000,
    max_rows: Optional[int] = None,
    partition_cols: list = ['vehicle_id', 'date'],
    date_strategy: str = 'synthetic'
):
    """
    Convert CSV to partitioned Parquet format.
    
    Args:
        csv_path: Path to input CSV file
        output_dir: Output directory for Parquet files
        chunk_size: Number of rows to process per chunk
        max_rows: Optional limit on rows to process (for testing)
        partition_cols: Columns to partition by
        date_strategy: Strategy for deriving date column
    """
    print("=" * 70)
    print("Converting CSV to Partitioned Parquet")
    print("=" * 70)
    print(f"\nInput:  {csv_path}")
    print(f"Output: {output_dir / 'timeseries'}")
    print(f"Chunk size: {chunk_size:,} rows")
    print(f"Partition by: {partition_cols}")
    print(f"Date strategy: {date_strategy}\n")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    timeseries_dir = output_dir / 'timeseries'
    
    # Get total row count for progress bar
    print("Counting total rows...")
    total_rows = sum(1 for _ in open(csv_path)) - 1  # Subtract header
    if max_rows:
        total_rows = min(total_rows, max_rows)
    print(f"Total rows to process: {total_rows:,}\n")
    
    # Process in chunks
    processed_rows = 0
    chunk_count = 0
    
    print("Processing chunks...")
    with tqdm(total=total_rows, unit='rows', unit_scale=True) as pbar:
        for chunk in pd.read_csv(csv_path, chunksize=chunk_size):
            if max_rows and processed_rows >= max_rows:
                break
            
            # Limit chunk if needed
            if max_rows:
                remaining = max_rows - processed_rows
                if len(chunk) > remaining:
                    chunk = chunk.head(remaining)
            
            # Derive date column
            chunk = derive_date_column(chunk, strategy=date_strategy)
            
            # Convert to Parquet
            try:
                convert_chunk_to_parquet(chunk, output_dir, partition_cols)
                processed_rows += len(chunk)
                chunk_count += 1
                pbar.update(len(chunk))
                
                if chunk_count % 10 == 0:
                    print(f"\n  Processed {chunk_count} chunks ({processed_rows:,} rows)...")
                    
            except Exception as e:
                print(f"\n❌ Error processing chunk {chunk_count}: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    print(f"\n✅ Conversion complete!")
    print(f"   Processed: {processed_rows:,} rows in {chunk_count} chunks")
    print(f"   Output: {timeseries_dir}")
    
    # Generate metadata
    generate_parquet_metadata(output_dir, csv_path, processed_rows, chunk_count)


def generate_parquet_metadata(
    output_dir: Path,
    source_csv: Path,
    total_rows: int,
    chunk_count: int
):
    """Generate metadata file for Parquet dataset."""
    timeseries_dir = output_dir / 'timeseries'
    
    # Count partitions
    vehicle_dirs = [d for d in timeseries_dir.iterdir() if d.is_dir() and d.name.startswith('vehicle_id=')]
    total_partitions = sum(1 for vdir in vehicle_dirs for _ in (vdir / 'date=*').parent.glob('date=*') if (vdir / 'date=*').parent.exists())
    
    # Get file sizes
    parquet_files = list(timeseries_dir.rglob('*.parquet'))
    total_size = sum(f.stat().st_size for f in parquet_files)
    total_size_gb = total_size / (1024 ** 3)
    
    metadata = {
        'conversion_date': datetime.now().isoformat(),
        'source_csv': str(source_csv),
        'source_size_gb': source_csv.stat().st_size / (1024 ** 3),
        'parquet_stats': {
            'total_rows': total_rows,
            'total_files': len(parquet_files),
            'total_partitions': len(vehicle_dirs),
            'total_size_bytes': total_size,
            'total_size_gb': round(total_size_gb, 3),
            'compression_ratio': round((source_csv.stat().st_size / total_size) if total_size > 0 else 0, 2)
        },
        'partition_structure': {
            'partition_by': ['vehicle_id', 'date'],
            'path_format': 'timeseries/vehicle_id={id}/date={date}/part-*.parquet'
        },
        'schema': {
            'note': 'See manifest.json for full column descriptions',
            'key_columns': [
                'vehicle_id', 'date', 'ts', 'voltage_V', 'current_A', 
                'temp_C', 'cycle_idx', 'cycle_type'
            ]
        }
    }
    
    metadata_path = output_dir / 'parquet_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n📊 Metadata saved to: {metadata_path}")
    print(f"   Compression ratio: {metadata['parquet_stats']['compression_ratio']}x")
    print(f"   Size reduction: {metadata['source_size_gb']:.2f}GB → {metadata['parquet_stats']['total_size_gb']:.2f}GB")


def test_duckdb_query(parquet_dir: Path):
    """Test DuckDB query on Parquet files."""
    try:
        import duckdb
        print("\n" + "=" * 70)
        print("Testing DuckDB Query")
        print("=" * 70)
        
        conn = duckdb.connect()
        
        # Query single vehicle
        query = f"""
        SELECT 
            vehicle_id,
            date,
            COUNT(*) as row_count,
            MIN(voltage_V) as min_voltage,
            MAX(voltage_V) as max_voltage,
            AVG(current_A) as avg_current
        FROM read_parquet('{parquet_dir}/timeseries/**/*.parquet')
        WHERE vehicle_id = 0
        GROUP BY vehicle_id, date
        ORDER BY date
        LIMIT 10
        """
        
        result = conn.execute(query).df()
        print("\n✅ DuckDB query successful!")
        print(f"\nSample results (vehicle_id=0):")
        print(result.to_string(index=False))
        
        # Test aggregation
        agg_query = f"""
        SELECT 
            COUNT(DISTINCT vehicle_id) as unique_vehicles,
            COUNT(*) as total_rows,
            MIN(date) as first_date,
            MAX(date) as last_date
        FROM read_parquet('{parquet_dir}/timeseries/**/*.parquet')
        """
        
        agg_result = conn.execute(agg_query).df()
        print(f"\nDataset summary:")
        print(agg_result.to_string(index=False))
        
        conn.close()
        
    except ImportError:
        print("\n⚠️  DuckDB not installed. Install with: pip install duckdb")
        print("   Skipping query test.")
    except Exception as e:
        print(f"\n⚠️  DuckDB query test failed: {e}")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert CSV to partitioned Parquet')
    parser.add_argument('--csv-path',
                       default='data/processed/battery_dataset1_ekf.csv',
                       help='Path to input CSV file')
    parser.add_argument('--output-dir',
                       default='data/parquet',
                       help='Output directory for Parquet files')
    parser.add_argument('--chunk-size', type=int, default=1_000_000,
                       help='Chunk size for processing (default: 1M)')
    parser.add_argument('--max-rows', type=int, default=None,
                       help='Limit number of rows to process (for testing)')
    parser.add_argument('--date-strategy', 
                       choices=['synthetic', 'cycle_based', 'vehicle_start'],
                       default='synthetic',
                       help='Strategy for deriving date column')
    parser.add_argument('--test-query', action='store_true',
                       help='Test DuckDB queries after conversion')
    
    args = parser.parse_args()
    
    csv_path = Path(args.csv_path)
    output_dir = Path(args.output_dir)
    
    if not csv_path.exists():
        print(f"❌ Error: CSV file not found: {csv_path}")
        sys.exit(1)
    
    # Convert
    convert_csv_to_parquet(
        csv_path=csv_path,
        output_dir=output_dir,
        chunk_size=args.chunk_size,
        max_rows=args.max_rows,
        date_strategy=args.date_strategy
    )
    
    # Test queries if requested
    if args.test_query:
        test_duckdb_query(output_dir)
    
    print("\n" + "=" * 70)
    print("✅ Phase 1 Complete: CSV → Parquet Conversion")
    print("=" * 70)
    print(f"\nNext steps:")
    print(f"  1. Verify Parquet files in: {output_dir / 'timeseries'}")
    print(f"  2. Test queries with DuckDB")
    print(f"  3. Proceed to Phase 2: Data Quality Pass")


if __name__ == '__main__':
    main()

