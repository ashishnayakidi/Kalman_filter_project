"""
Convert full battery_dataset1 to ProductA EKF-compatible format.

This script processes all 629k pickle files and converts them to CSV format
compatible with the EKF pipeline (run_replay.py).

Output format matches tick_stream expectations:
- voltage_V, current_A, temp_C (EKF inputs)
- dt_s, time_s (time calculations)
- cycle_idx, cycle_type (cycle information)
- Additional metadata preserved
"""
import torch
import numpy as np
import pandas as pd
from pathlib import Path
import tarfile
from collections import OrderedDict
from typing import Optional
import sys
from tqdm import tqdm


def load_pickle_file(pkl_path: Path) -> tuple:
    """Load a pickle file using PyTorch with weights_only=False."""
    return torch.load(pkl_path, map_location='cpu', weights_only=False)


def convert_to_ekf_format(
    data_dir: Path,
    output_csv: Path,
    label_csv: Optional[Path] = None,
    batch_size: int = 10000,
    max_files: Optional[int] = None
):
    """
    Convert pickle files to EKF-compatible CSV format.
    
    Processes files in batches to handle large dataset efficiently.
    
    Args:
        data_dir: Directory containing .pkl files
        output_csv: Output CSV path
        label_csv: Optional label CSV file
        batch_size: Number of files to process before writing to CSV
        max_files: Optional limit on number of files (None = all files)
    """
    pkl_files = sorted(list(data_dir.glob("*.pkl")))
    
    if max_files:
        pkl_files = pkl_files[:max_files]
    
    total_files = len(pkl_files)
    print("=" * 70)
    print("Converting Full Dataset to EKF Format")
    print("=" * 70)
    print(f"\nTotal files to process: {total_files:,}")
    print(f"Expected output rows: {total_files * 128:,}")
    print(f"Batch size: {batch_size:,} files")
    print(f"Output: {output_csv}\n")
    
    # Load labels if available
    labels_dict = {}
    if label_csv and label_csv.exists():
        df_labels = pd.read_csv(label_csv)
        if 'car' in df_labels.columns and 'label' in df_labels.columns:
            labels_dict = dict(zip(df_labels['car'], df_labels['label']))
            print(f"Loaded {len(labels_dict)} labels from {label_csv.name}\n")
    
    # Process in batches
    all_dfs = []
    errors = []
    file_counter = 0
    
    # Open CSV file for writing (append mode)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    first_batch = True
    
    with tqdm(total=total_files, desc="Processing files", unit="files") as pbar:
        batch_rows = []
        
        for pkl_file in pkl_files:
            try:
                data = load_pickle_file(pkl_file)
                
                if not isinstance(data, tuple) or len(data) != 2:
                    errors.append(f"{pkl_file.name}: Invalid structure")
                    pbar.update(1)
                    continue
                
                ts_array = data[0]
                metadata = data[1]
                
                if not isinstance(ts_array, np.ndarray) or ts_array.shape != (128, 8):
                    errors.append(f"{pkl_file.name}: Invalid array shape")
                    pbar.update(1)
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
                
                # Use charge_segment as cycle_idx, or create sequential
                try:
                    cycle_idx = int(charge_segment) if charge_segment else 0
                except:
                    cycle_idx = 0
                
                # All currents are negative (discharge), so cycle_type is 'discharge'
                cycle_type = 'discharge'
                
                # Extract features
                voltage_data = ts_array[:, 0]  # Column 0: Voltage
                current_data = ts_array[:, 1]  # Column 1: Current (negative = discharge)
                temp_data = ts_array[:, 2]     # Column 2: Temperature
                
                # Convert current: make positive for discharge (EKF expects positive for discharge)
                current_data_ekf = -current_data  # Negate to make positive
                
                # Calculate time
                # Assume dt_s = 1.0 second per sample (can be adjusted based on time_index if needed)
                dt_s = 1.0
                time_steps = np.arange(128) * dt_s
                
                # Create rows for each time step
                for time_idx in range(128):
                    row = {
                        # EKF required fields
                        'voltage_V': float(voltage_data[time_idx]),
                        'current_A': float(current_data_ekf[time_idx]),  # Positive for discharge
                        'temp_C': float(temp_data[time_idx]),
                        'dt_s': dt_s,
                        'time_s': float(time_steps[time_idx]),
                        
                        # Cycle information
                        'cycle_idx': cycle_idx,
                        'cycle_type': cycle_type,
                        
                        # Metadata
                        'car_id': car_id,
                        'sample_idx': time_idx,
                        'label': label,
                        'charge_segment': charge_segment,
                        'mileage': mileage,
                        'capacity': capacity,
                        
                        # Additional features (preserved for analysis)
                        'voltage_2': float(ts_array[time_idx, 3]),
                        'voltage_3': float(ts_array[time_idx, 4]),
                        'feature_5': float(ts_array[time_idx, 5]),
                        'feature_6': float(ts_array[time_idx, 6]),
                        'time_index': float(ts_array[time_idx, 7]),
                    }
                    
                    batch_rows.append(row)
                
                file_counter += 1
                pbar.update(1)
                
                # Write batch when it reaches batch_size
                if len(batch_rows) >= batch_size * 128:
                    df_batch = pd.DataFrame(batch_rows)
                    
                    # Reorder columns for EKF compatibility
                    column_order = [
                        'voltage_V', 'current_A', 'temp_C', 'dt_s', 'time_s',
                        'cycle_idx', 'cycle_type',
                        'car_id', 'sample_idx', 'label',
                        'voltage_2', 'voltage_3', 'feature_5', 'feature_6', 'time_index',
                        'charge_segment', 'mileage', 'capacity'
                    ]
                    df_batch = df_batch[[col for col in column_order if col in df_batch.columns]]
                    
                    # Write to CSV (append mode after first batch)
                    if first_batch:
                        df_batch.to_csv(output_csv, index=False, mode='w')
                        first_batch = False
                    else:
                        df_batch.to_csv(output_csv, index=False, mode='a', header=False)
                    
                    pbar.set_postfix({
                        'rows': f"{len(batch_rows):,}",
                        'files': f"{file_counter:,}"
                    })
                    batch_rows = []
                    
            except Exception as e:
                errors.append(f"{pkl_file.name}: {str(e)}")
                pbar.update(1)
                continue
        
        # Write remaining rows
        if batch_rows:
            df_batch = pd.DataFrame(batch_rows)
            column_order = [
                'voltage_V', 'current_A', 'temp_C', 'dt_s', 'time_s',
                'cycle_idx', 'cycle_type',
                'car_id', 'sample_idx', 'label',
                'voltage_2', 'voltage_3', 'feature_5', 'feature_6', 'time_index',
                'charge_segment', 'mileage', 'capacity'
            ]
            df_batch = df_batch[[col for col in column_order if col in df_batch.columns]]
            
            if first_batch:
                df_batch.to_csv(output_csv, index=False, mode='w')
            else:
                df_batch.to_csv(output_csv, index=False, mode='a', header=False)
    
    print(f"\n✅ Conversion complete!")
    print(f"   Output: {output_csv}")
    print(f"   Files processed: {file_counter:,}/{total_files:,}")
    print(f"   Expected rows: {file_counter * 128:,}")
    
    if errors:
        print(f"\n⚠️  {len(errors)} files had errors (first 10):")
        for err in errors[:10]:
            print(f"   - {err}")
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more errors")
    
    # Verify output
    print(f"\n📊 Verifying output file...")
    try:
        df_sample = pd.read_csv(output_csv, nrows=1000)
        print(f"   Sample rows: {len(df_sample)}")
        print(f"   Columns: {list(df_sample.columns)}")
        print(f"   Required EKF columns present: {all(col in df_sample.columns for col in ['voltage_V', 'current_A', 'temp_C', 'dt_s', 'time_s'])}")
        print(f"   Current range: {df_sample['current_A'].min():.2f} to {df_sample['current_A'].max():.2f} A")
        print(f"   Voltage range: {df_sample['voltage_V'].min():.2f} to {df_sample['voltage_V'].max():.2f} V")
        print(f"   Temperature range: {df_sample['temp_C'].min():.2f} to {df_sample['temp_C'].max():.2f} °C")
    except Exception as e:
        print(f"   ⚠️  Could not verify output: {e}")
    
    return output_csv


def main():
    """Main conversion function."""
    dataset_path = Path.home() / "Downloads" / "battery_dataset1.tar.gz"
    temp_dir = Path("/tmp/battery_dataset_analysis")
    temp_dir.mkdir(exist_ok=True)
    
    # Extract dataset if needed
    dataset_root = temp_dir / "battery_dataset1"
    if not dataset_root.exists():
        print("Extracting dataset (this may take a few minutes)...")
        with tarfile.open(dataset_path, 'r:gz') as tar:
            tar.extractall(temp_dir)
        print("✅ Extraction complete\n")
    
    data_dir = dataset_root / "data"
    label_csv = dataset_root / "label" / "label.csv"
    
    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}")
        sys.exit(1)
    
    # Output to data/processed directory (matching project structure)
    output_dir = Path(__file__).parent.parent / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / "battery_dataset1_ekf.csv"
    
    print(f"Output will be saved to: {output_csv}")
    print(f"This will process all files and may take 30-60 minutes...\n")
    
    # Process full dataset
    convert_to_ekf_format(
        data_dir,
        output_csv,
        label_csv,
        batch_size=10000,  # Process 10k files at a time
        max_files=None      # Process all files
    )
    
    print(f"\n✅ Full dataset conversion complete!")
    print(f"   Ready for EKF processing: {output_csv}")
    print(f"\n   To test with EKF, run:")
    print(f"   python scripts/run_replay.py --csv-path {output_csv}")


if __name__ == "__main__":
    main()

