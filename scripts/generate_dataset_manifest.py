"""
Generate dataset manifest and quality report for Phase 0: Freeze Dataset.

This script analyzes the processed CSV and creates:
1. manifest.json - Complete dataset metadata
2. quality_report.json - Data quality metrics
3. README.md - Dataset documentation
"""
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import hashlib
import sys


def calculate_file_hash(file_path: Path, chunk_size: int = 8192) -> str:
    """Calculate SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


def analyze_dataset(csv_path: Path) -> Dict[str, Any]:
    """Analyze the processed CSV dataset and extract metadata."""
    print(f"Analyzing dataset: {csv_path}")
    
    # Read sample to get column info
    print("  Reading sample rows...")
    df_sample = pd.read_csv(csv_path, nrows=10000)
    
    # Get total row count (efficiently)
    print("  Counting total rows...")
    total_rows = sum(1 for _ in open(csv_path)) - 1  # Subtract header
    
    # Read full dataset for statistics (in chunks to avoid memory issues)
    print("  Computing statistics (this may take a while)...")
    chunk_size = 1_000_000
    chunks = []
    stats = {}
    
    for i, chunk in enumerate(pd.read_csv(csv_path, chunksize=chunk_size)):
        if i == 0:
            # Initialize stats from first chunk
            for col in chunk.columns:
                if pd.api.types.is_numeric_dtype(chunk[col]):
                    stats[col] = {
                        'min': float('inf'),
                        'max': float('-inf'),
                        'sum': 0.0,
                        'count': 0,
                        'null_count': 0
                    }
        
        # Update stats
        for col in chunk.columns:
            if col in stats:
                col_data = chunk[col].dropna()
                if len(col_data) > 0:
                    stats[col]['min'] = min(stats[col]['min'], float(col_data.min()))
                    stats[col]['max'] = max(stats[col]['max'], float(col_data.max()))
                    stats[col]['sum'] += float(col_data.sum())
                    stats[col]['count'] += len(col_data)
                stats[col]['null_count'] += chunk[col].isna().sum()
        
        chunks.append(chunk)
        if i % 10 == 0:
            print(f"    Processed {i * chunk_size:,} rows...")
    
    # Calculate final statistics
    print("  Computing final statistics...")
    column_stats = {}
    missing_rates = {}
    
    for col in df_sample.columns:
        col_type = str(df_sample[col].dtype)
        null_count = stats.get(col, {}).get('null_count', 0)
        missing_rate = null_count / total_rows if total_rows > 0 else 0.0
        
        col_info = {
            'type': col_type,
            'description': get_column_description(col),
            'unit': get_column_unit(col),
            'missing_rate': round(missing_rate, 6),
            'null_count': int(null_count)
        }
        
        if col in stats:
            col_info['min'] = stats[col]['min'] if stats[col]['min'] != float('inf') else None
            col_info['max'] = stats[col]['max'] if stats[col]['max'] != float('-inf') else None
            if stats[col]['count'] > 0:
                col_info['mean'] = round(stats[col]['sum'] / stats[col]['count'], 4)
        
        column_stats[col] = col_info
        missing_rates[col] = missing_rate
    
    # Get unique values for categorical columns
    print("  Analyzing categorical columns...")
    for col in ['cycle_type', 'label']:
        if col in df_sample.columns:
            unique_vals = df_sample[col].unique()[:20]  # Limit to first 20
            column_stats[col]['unique_values'] = [str(v) for v in unique_vals]
            column_stats[col]['unique_count'] = int(df_sample[col].nunique())
    
    # Get vehicle and cycle statistics
    print("  Computing vehicle and cycle statistics...")
    vehicle_stats = {}
    if 'car_id' in df_sample.columns:
        # Read vehicle IDs in chunks
        vehicle_ids = set()
        cycle_ids = set()
        for chunk in pd.read_csv(csv_path, chunksize=chunk_size, usecols=['car_id', 'cycle_idx']):
            vehicle_ids.update(chunk['car_id'].dropna().unique())
            cycle_ids.update(chunk['cycle_idx'].dropna().unique())
        
        vehicle_stats = {
            'unique_vehicles': len(vehicle_ids),
            'vehicle_id_range': [int(min(vehicle_ids)), int(max(vehicle_ids))] if vehicle_ids else None,
            'unique_cycles': len(cycle_ids),
            'cycle_range': [int(min(cycle_ids)), int(max(cycle_ids))] if cycle_ids else None
        }
    
    return {
        'total_rows': total_rows,
        'total_columns': len(df_sample.columns),
        'columns': column_stats,
        'missing_rates': missing_rates,
        'vehicle_stats': vehicle_stats,
        'sample_data': df_sample.head(5).to_dict('records')
    }


def get_column_description(col: str) -> str:
    """Get human-readable description for a column."""
    descriptions = {
        'voltage_V': 'Voltage measurement in Volts',
        'current_A': 'Current measurement in Amperes (positive for discharge)',
        'temp_C': 'Temperature measurement in Celsius',
        'dt_s': 'Time step duration in seconds',
        'time_s': 'Cumulative time in seconds (relative to cycle start)',
        'cycle_idx': 'Cycle index identifier',
        'cycle_type': 'Type of cycle (discharge, charge, etc.)',
        'car_id': 'Vehicle/car identifier',
        'sample_idx': 'Sample index within cycle (0-127)',
        'label': 'Classification label (binary)',
        'charge_segment': 'Charge segment identifier',
        'mileage': 'Vehicle mileage in kilometers',
        'capacity': 'Battery capacity in Ah',
        'voltage_2': 'Secondary voltage measurement',
        'voltage_3': 'Tertiary voltage measurement',
        'feature_5': 'Additional feature 5',
        'feature_6': 'Additional feature 6',
        'time_index': 'Time index from original data'
    }
    return descriptions.get(col, f'{col} column')


def get_column_unit(col: str) -> str:
    """Get unit for a column."""
    units = {
        'voltage_V': 'V',
        'current_A': 'A',
        'temp_C': '°C',
        'dt_s': 's',
        'time_s': 's',
        'mileage': 'km',
        'capacity': 'Ah'
    }
    return units.get(col, '')


def generate_manifest(
    csv_path: Path,
    output_dir: Path,
    source_info: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate complete manifest.json."""
    print("\n" + "=" * 70)
    print("Generating Dataset Manifest")
    print("=" * 70)
    
    # Analyze dataset
    analysis = analyze_dataset(csv_path)
    
    # Calculate file hash
    print("\n  Calculating file hash...")
    file_hash = calculate_file_hash(csv_path)
    
    # Get file size
    file_size_bytes = csv_path.stat().st_size
    file_size_gb = file_size_bytes / (1024 ** 3)
    
    # Build manifest
    manifest = {
        'version': 'v0',
        'processing_date': datetime.now().isoformat(),
        'source': source_info,
        'file_info': {
            'path': str(csv_path.relative_to(csv_path.parent.parent)),
            'size_bytes': file_size_bytes,
            'size_gb': round(file_size_gb, 3),
            'sha256': file_hash,
            'format': 'CSV',
            'encoding': 'UTF-8'
        },
        'dataset_stats': {
            'total_rows': analysis['total_rows'],
            'total_columns': analysis['total_columns'],
            'unique_vehicles': analysis['vehicle_stats'].get('unique_vehicles', 0),
            'unique_cycles': analysis['vehicle_stats'].get('unique_cycles', 0),
            'vehicle_id_range': analysis['vehicle_stats'].get('vehicle_id_range'),
            'cycle_range': analysis['vehicle_stats'].get('cycle_range')
        },
        'columns': analysis['columns'],
        'missing_rates': analysis['missing_rates'],
        'sampling_rate_hz': 1.0,
        'date_range': {
            'note': 'Timestamps are relative (time_s), not absolute UTC. Date range not available from source data.'
        },
        'scripts_used': [
            'convert_battery_dataset_full.py',
            'test_ekf_with_battery_dataset.py'
        ],
        'license': 'CC BY-NC-SA (assumed from research paper)',
        'notes': [
            'Current values converted from negative (discharge) to positive for EKF compatibility',
            'Time stamps are relative (time_s) within each cycle, not absolute UTC',
            'Temperature units assumed to be Celsius (verify if values >50°C)',
            'All cycles are discharge cycles (cycle_type = "discharge")'
        ]
    }
    
    # Save manifest
    manifest_path = output_dir / 'manifest.json'
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n✅ Manifest saved to: {manifest_path}")
    return manifest, analysis


def generate_quality_report(analysis: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
    """Generate quality report with detailed statistics."""
    print("\n" + "=" * 70)
    print("Generating Quality Report")
    print("=" * 70)
    
    quality_report = {
        'generated_at': datetime.now().isoformat(),
        'total_rows': analysis['total_rows'],
        'data_quality': {
            'missing_data': {
                col: {
                    'missing_rate': rate,
                    'missing_count': int(rate * analysis['total_rows']),
                    'severity': 'high' if rate > 0.1 else 'medium' if rate > 0.01 else 'low'
                }
                for col, rate in analysis['missing_rates'].items()
                if rate > 0
            },
            'columns_with_missing_data': sum(1 for r in analysis['missing_rates'].values() if r > 0),
            'total_missing_cells': sum(int(r * analysis['total_rows']) for r in analysis['missing_rates'].values())
        },
        'value_ranges': {
            col: {
                'min': info.get('min'),
                'max': info.get('max'),
                'mean': info.get('mean'),
                'plausible': check_plausibility(col, info)
            }
            for col, info in analysis['columns'].items()
            if 'min' in info and 'max' in info
        },
        'recommendations': generate_quality_recommendations(analysis)
    }
    
    # Save quality report
    quality_path = output_dir / 'quality_report.json'
    with open(quality_path, 'w') as f:
        json.dump(quality_report, f, indent=2)
    
    print(f"✅ Quality report saved to: {quality_path}")
    return quality_report


def check_plausibility(col: str, info: Dict) -> Dict[str, Any]:
    """Check if values are within plausible ranges."""
    checks = {}
    
    if col == 'voltage_V':
        # Li-ion batteries: 3.0V - 4.5V typical
        checks['in_range'] = 3.0 <= info.get('min', 0) <= 4.5 and 3.0 <= info.get('max', 0) <= 4.5
        checks['expected_range'] = '3.0-4.5V'
    
    elif col == 'current_A':
        # Current should be positive (discharge) after conversion
        checks['all_positive'] = info.get('min', 0) >= 0
        checks['expected_range'] = '>= 0A (discharge)'
    
    elif col == 'temp_C':
        # Battery temperature: -20°C to 60°C typical operating range
        checks['in_range'] = -20 <= info.get('min', 0) <= 100 and -20 <= info.get('max', 0) <= 100
        checks['expected_range'] = '-20°C to 60°C (operating), up to 100°C (extreme)'
        if info.get('max', 0) > 60:
            checks['warning'] = 'Some temperatures exceed 60°C - verify units'
    
    return checks


def generate_quality_recommendations(analysis: Dict[str, Any]) -> list:
    """Generate data quality recommendations."""
    recommendations = []
    
    # Check missing data
    high_missing = [col for col, rate in analysis['missing_rates'].items() if rate > 0.1]
    if high_missing:
        recommendations.append({
            'issue': 'High missing data rate',
            'columns': high_missing,
            'action': 'Investigate source data and consider imputation or exclusion'
        })
    
    # Check value ranges
    for col, info in analysis['columns'].items():
        plausibility = check_plausibility(col, info)
        if 'warning' in plausibility:
            recommendations.append({
                'issue': plausibility['warning'],
                'column': col,
                'action': 'Verify data units and source'
            })
    
    return recommendations


def generate_readme(manifest: Dict[str, Any], output_dir: Path):
    """Generate README.md for the dataset."""
    readme_content = f"""# Battery Dataset v0

## Overview

This is the frozen version 0 of the battery dataset, processed and ready for EKF analysis.

**Processing Date**: {manifest['processing_date']}

## Source

- **Original Dataset**: {manifest['source'].get('name', 'battery_dataset1.tar.gz')}
- **Source Location**: {manifest['source'].get('location', 'Research paper dataset')}
- **License**: {manifest['license']}
- **Total Files Processed**: {manifest['source'].get('total_files', 629121):,} pickle files
- **Total Rows**: {manifest['dataset_stats']['total_rows']:,}
- **Unique Vehicles**: {manifest['dataset_stats']['unique_vehicles']}
- **Unique Cycles**: {manifest['dataset_stats']['unique_cycles']}

## File Information

- **File**: {manifest['file_info']['path']}
- **Size**: {manifest['file_info']['size_gb']:.2f} GB
- **Format**: {manifest['file_info']['format']}
- **SHA256**: `{manifest['file_info']['sha256'][:16]}...` (see manifest.json for full hash)

## Data Schema

### Core EKF Columns

- `voltage_V`: Voltage measurement (V)
- `current_A`: Current measurement (A) - positive for discharge
- `temp_C`: Temperature (°C)
- `dt_s`: Time step (s)
- `time_s`: Cumulative time (s) - relative to cycle start

### Cycle Information

- `cycle_idx`: Cycle index
- `cycle_type`: Type of cycle (all "discharge" in this dataset)
- `car_id`: Vehicle identifier

### Metadata

- `label`: Classification label
- `charge_segment`: Charge segment identifier
- `mileage`: Vehicle mileage (km)
- `capacity`: Battery capacity (Ah)

See `manifest.json` for complete column descriptions and statistics.

## Processing Scripts

The following scripts were used to process this dataset:

{chr(10).join(f'- `{script}`' for script in manifest['scripts_used'])}

Scripts are available in `scripts/` directory.

## Data Quality

See `quality_report.json` for detailed quality metrics including:
- Missing data rates per column
- Value range checks
- Plausibility checks
- Quality recommendations

## Usage

### Load with Pandas

```python
import pandas as pd

# Load full dataset (large - 10GB)
df = pd.read_csv('data/processed/battery_dataset1_ekf.csv')

# Load in chunks (recommended)
chunk_size = 1_000_000
for chunk in pd.read_csv('data/processed/battery_dataset1_ekf.csv', chunksize=chunk_size):
    # Process chunk
    pass
```

### Use with EKF Pipeline

```bash
# Test with sample
python scripts/test_ekf_with_battery_dataset.py --csv-path data/processed/battery_dataset1_ekf.csv --max-ticks 500

# Full processing
python scripts/run_replay.py --csv-path data/processed/battery_dataset1_ekf.csv
```

## Notes

{chr(10).join(f'- {note}' for note in manifest['notes'])}

## Version History

- **v0** ({manifest['processing_date'][:10]}): Initial frozen version
  - Converted from 629k pickle files
  - EKF-compatible format
  - Quality checks performed

## License

{manifest['license']}

---

For detailed metadata, see `manifest.json`.
For quality metrics, see `quality_report.json`.
"""
    
    readme_path = output_dir / 'README.md'
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    
    print(f"✅ README saved to: {readme_path}")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate dataset manifest and quality report')
    parser.add_argument('--csv-path', 
                       default='data/processed/battery_dataset1_ekf.csv',
                       help='Path to processed CSV file')
    parser.add_argument('--output-dir',
                       default='dataset_v0',
                       help='Output directory for manifest and reports')
    
    args = parser.parse_args()
    
    csv_path = Path(args.csv_path)
    output_dir = Path(args.output_dir)
    
    if not csv_path.exists():
        print(f"❌ Error: CSV file not found: {csv_path}")
        sys.exit(1)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Source information
    source_info = {
        'name': 'battery_dataset1.tar.gz',
        'location': 'Research paper dataset (originally from ~/Downloads/)',
        'total_files': 629121,
        'format': 'PyTorch pickle files (.pkl)',
        'extraction_date': '2024-11-16'
    }
    
    # Generate manifest
    manifest, analysis = generate_manifest(csv_path, output_dir, source_info)
    
    # Generate quality report
    quality_report = generate_quality_report(analysis, output_dir)
    
    # Generate README
    generate_readme(manifest, output_dir)
    
    print("\n" + "=" * 70)
    print("✅ Phase 0 Complete: Dataset Frozen")
    print("=" * 70)
    print(f"\nGenerated files:")
    print(f"  - {output_dir / 'manifest.json'}")
    print(f"  - {output_dir / 'quality_report.json'}")
    print(f"  - {output_dir / 'README.md'}")
    print(f"\nNext steps:")
    print(f"  1. Review manifest.json and quality_report.json")
    print(f"  2. Copy processing scripts to {output_dir / 'scripts'}/")
    print(f"  3. Proceed to Phase 1: Convert to Parquet")


if __name__ == '__main__':
    main()

