"""
Comprehensive analysis script for battery_dataset1.tar.gz

Dataset Structure:
- Each .pkl file contains a tuple of 2 elements:
  1. Time-series array: (128, 8) numpy array with 8 features over 128 time steps
  2. Metadata: OrderedDict with label, car, charge_segment, mileage, capacity

Time-series Features (8 columns):
  Col 0: Voltage (V) - ~3.86-4.14V
  Col 1: Current (A) - negative values indicate discharge
  Col 2: Temperature (°C or °F) - typically 50-100 range
  Col 3: Voltage 2 (V) - possibly pack voltage or another cell
  Col 4: Voltage 3 (V) - possibly another cell voltage
  Col 5: Unknown feature (constant or slowly varying)
  Col 6: Unknown feature (constant or slowly varying)
  Col 7: Time index or duration (0-1270)
"""
import torch
import numpy as np
import pandas as pd
from pathlib import Path
import tarfile
from collections import OrderedDict
from typing import Dict, List, Optional
import sys


def load_pickle_file(pkl_path: Path) -> tuple:
    """Load a pickle file using PyTorch with weights_only=False."""
    return torch.load(pkl_path, map_location='cpu', weights_only=False)


def analyze_dataset_structure(data_dir: Path, num_samples: int = 10):
    """Analyze the structure of pickle files in the dataset."""
    pkl_files = sorted(list(data_dir.glob("*.pkl")))[:num_samples]
    
    print("=" * 70)
    print("Dataset Structure Analysis")
    print("=" * 70)
    print(f"\nAnalyzing {len(pkl_files)} sample files...\n")
    
    all_stats = []
    feature_stats = {i: {'min': [], 'max': [], 'mean': [], 'std': []} for i in range(8)}
    
    for pkl_file in pkl_files:
        try:
            data = load_pickle_file(pkl_file)
            
            if not isinstance(data, tuple) or len(data) != 2:
                print(f"⚠️  {pkl_file.name}: Unexpected structure")
                continue
            
            ts_array = data[0]  # Time-series data
            metadata = data[1]  # Metadata
            
            if not isinstance(ts_array, np.ndarray) or ts_array.shape != (128, 8):
                print(f"⚠️  {pkl_file.name}: Unexpected array shape {ts_array.shape if hasattr(ts_array, 'shape') else 'N/A'}")
                continue
            
            # Collect statistics
            for col in range(8):
                col_data = ts_array[:, col]
                feature_stats[col]['min'].append(col_data.min())
                feature_stats[col]['max'].append(col_data.max())
                feature_stats[col]['mean'].append(col_data.mean())
                feature_stats[col]['std'].append(col_data.std())
            
            all_stats.append({
                'file': pkl_file.name,
                'metadata': metadata
            })
            
        except Exception as e:
            print(f"❌ Error loading {pkl_file.name}: {e}")
    
    # Print feature analysis
    print("\n" + "=" * 70)
    print("Time-Series Features Analysis (8 columns, 128 time steps)")
    print("=" * 70)
    
    feature_names = [
        "Voltage 1 (V)",
        "Current (A)",
        "Temperature (°C/°F)",
        "Voltage 2 (V)",
        "Voltage 3 (V)",
        "Feature 5",
        "Feature 6",
        "Time Index"
    ]
    
    for col in range(8):
        stats = feature_stats[col]
        print(f"\nColumn {col}: {feature_names[col]}")
        print(f"  Min: {min(stats['min']):.3f}, Max: {max(stats['max']):.3f}")
        print(f"  Mean range: {min(stats['mean']):.3f} to {max(stats['mean']):.3f}")
        print(f"  Std range: {min(stats['std']):.3f} to {max(stats['std']):.3f}")
    
    # Print metadata analysis
    print("\n" + "=" * 70)
    print("Metadata Analysis")
    print("=" * 70)
    
    if all_stats:
        metadata_keys = list(all_stats[0]['metadata'].keys())
        print(f"\nMetadata keys: {metadata_keys}")
        
        for key in metadata_keys:
            values = [s['metadata'].get(key) for s in all_stats]
            print(f"\n  {key}:")
            print(f"    Sample values: {values[:5]}")
            if all(isinstance(v, (int, float)) for v in values if v is not None):
                numeric_vals = [v for v in values if v is not None]
                print(f"    Range: {min(numeric_vals)} to {max(numeric_vals)}")
                print(f"    Mean: {np.mean(numeric_vals):.2f}")
    
    return all_stats, feature_stats


def convert_to_product_a_format(
    data_dir: Path,
    output_csv: Path,
    label_csv: Optional[Path] = None,
    max_files: Optional[int] = None
):
    """
    Convert pickle files to CSV format suitable for ProductA EKF processing.
    
    Output format:
    - car_id: Vehicle identifier
    - sample_idx: Time step index (0-127)
    - voltage: Voltage measurement (V)
    - current: Current measurement (A)
    - temperature: Temperature measurement
    - voltage_2: Second voltage measurement (V)
    - voltage_3: Third voltage measurement (V)
    - feature_5: Unknown feature 5
    - feature_6: Unknown feature 6
    - time_index: Time index from column 7
    - label: Classification label (from metadata or label CSV)
    - charge_segment: Charge segment ID
    - mileage: Vehicle mileage
    - capacity: Battery capacity (Ah)
    """
    pkl_files = sorted(list(data_dir.glob("*.pkl")))
    
    if max_files:
        pkl_files = pkl_files[:max_files]
    
    print("=" * 70)
    print("Converting Dataset to ProductA Format")
    print("=" * 70)
    print(f"\nProcessing {len(pkl_files)} pickle files...")
    
    # Load labels if available
    labels_dict = {}
    if label_csv and label_csv.exists():
        df_labels = pd.read_csv(label_csv)
        # Handle different CSV formats
        if 'car' in df_labels.columns and 'label' in df_labels.columns:
            labels_dict = dict(zip(df_labels['car'], df_labels['label']))
            print(f"Loaded {len(labels_dict)} labels from {label_csv.name}")
    
    all_rows = []
    errors = []
    
    feature_names = [
        'voltage',
        'current',
        'temperature',
        'voltage_2',
        'voltage_3',
        'feature_5',
        'feature_6',
        'time_index'
    ]
    
    for idx, pkl_file in enumerate(pkl_files):
        try:
            data = load_pickle_file(pkl_file)
            
            if not isinstance(data, tuple) or len(data) != 2:
                errors.append(f"{pkl_file.name}: Invalid structure")
                continue
            
            ts_array = data[0]
            metadata = data[1]
            
            if not isinstance(ts_array, np.ndarray) or ts_array.shape != (128, 8):
                errors.append(f"{pkl_file.name}: Invalid array shape")
                continue
            
            # Extract metadata
            car_id = metadata.get('car', pkl_file.stem)
            label = metadata.get('label', labels_dict.get(car_id, None))
            charge_segment = metadata.get('charge_segment', None)
            mileage = metadata.get('mileage', None)
            capacity = metadata.get('capacity', None)
            
            # Convert label string to int if needed
            if isinstance(label, str):
                try:
                    label = int(label)
                except:
                    pass
            
            # Create rows for each time step
            for time_idx in range(128):
                row = {
                    'car_id': car_id,
                    'sample_idx': time_idx,
                    'label': label,
                    'charge_segment': charge_segment,
                    'mileage': mileage,
                    'capacity': capacity
                }
                
                # Add time-series features
                for col_idx, feature_name in enumerate(feature_names):
                    row[feature_name] = ts_array[time_idx, col_idx]
                
                all_rows.append(row)
            
            if (idx + 1) % 1000 == 0:
                print(f"  Processed {idx + 1}/{len(pkl_files)} files... ({len(all_rows)} rows)")
                
        except Exception as e:
            errors.append(f"{pkl_file.name}: {str(e)}")
            continue
    
    # Create DataFrame
    if all_rows:
        df = pd.DataFrame(all_rows)
        
        # Reorder columns for better readability
        column_order = [
            'car_id', 'sample_idx', 'label',
            'voltage', 'current', 'temperature',
            'voltage_2', 'voltage_3',
            'feature_5', 'feature_6', 'time_index',
            'charge_segment', 'mileage', 'capacity'
        ]
        df = df[[col for col in column_order if col in df.columns]]
        
        # Save to CSV
        df.to_csv(output_csv, index=False)
        
        print(f"\n✅ Conversion complete!")
        print(f"   Output: {output_csv}")
        print(f"   Total rows: {len(df):,}")
        print(f"   Unique vehicles: {df['car_id'].nunique()}")
        print(f"   Columns: {list(df.columns)}")
        print(f"   Shape: {df.shape}")
        
        if errors:
            print(f"\n⚠️  {len(errors)} files had errors (first 5):")
            for err in errors[:5]:
                print(f"   - {err}")
        
        return df
    else:
        print("\n❌ No data extracted from pickle files")
        return None


def main():
    """Main analysis and conversion function."""
    dataset_path = Path.home() / "Downloads" / "battery_dataset1.tar.gz"
    temp_dir = Path("/tmp/battery_dataset_analysis")
    temp_dir.mkdir(exist_ok=True)
    
    # Extract dataset if needed
    dataset_root = temp_dir / "battery_dataset1"
    if not dataset_root.exists():
        print("Extracting dataset...")
        with tarfile.open(dataset_path, 'r:gz') as tar:
            tar.extractall(temp_dir)
        print("✅ Extraction complete\n")
    
    data_dir = dataset_root / "data"
    label_csv = dataset_root / "label" / "label.csv"
    
    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}")
        sys.exit(1)
    
    # Step 1: Analyze structure
    print("\n" + "=" * 70)
    print("STEP 1: Dataset Structure Analysis")
    print("=" * 70)
    stats, feature_stats = analyze_dataset_structure(data_dir, num_samples=20)
    
    # Step 2: Convert to ProductA format
    print("\n\n" + "=" * 70)
    print("STEP 2: Converting to ProductA Format")
    print("=" * 70)
    
    # For initial testing, process a subset (e.g., 1000 files = 128k rows)
    # Remove max_files parameter to process all files
    output_csv = Path("/tmp/battery_dataset_producta.csv")
    df = convert_to_product_a_format(
        data_dir,
        output_csv,
        label_csv,
        max_files=1000  # Remove this to process all 629k files
    )
    
    if df is not None:
        print("\n" + "=" * 70)
        print("STEP 3: Data Summary")
        print("=" * 70)
        print("\nFirst 10 rows:")
        print(df.head(10))
        print("\nData types:")
        print(df.dtypes)
        print("\nBasic statistics:")
        print(df[['voltage', 'current', 'temperature']].describe())
        print(f"\n✅ Analysis complete! Output saved to: {output_csv}")
        print(f"\nTo process all files, remove the max_files parameter in the script.")


if __name__ == "__main__":
    main()

