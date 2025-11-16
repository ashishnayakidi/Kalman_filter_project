"""Load battery_dataset1 pickle files and convert to format suitable for Product A."""
import pickle
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Dict, List, Optional

try:
    import torch
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    print("PyTorch not available, using standard pickle loader")


def load_pickle_file(pkl_path: Path):
    """Load a pickle file, trying PyTorch first, then standard pickle."""
    if PYTORCH_AVAILABLE:
        try:
            # Use weights_only=False for research datasets (PyTorch 2.6+ default changed)
            return torch.load(pkl_path, map_location='cpu', weights_only=False)
        except:
            pass
    
    with open(pkl_path, 'rb') as f:
        return pickle.load(f)


def analyze_pickle_structure(data_dir: Path, num_samples: int = 5):
    """Analyze the structure of pickle files to understand data format."""
    pkl_files = list(data_dir.glob("*.pkl"))[:num_samples]
    
    print(f"Analyzing {len(pkl_files)} pickle files...")
    print("=" * 60)
    
    all_structures = []
    
    for pkl_file in pkl_files:
        try:
            data = load_pickle_file(pkl_file)
            structure = {}
            
            if isinstance(data, dict):
                structure['type'] = 'dict'
                structure['keys'] = list(data.keys())
                structure['data'] = {}
                
                for key, val in data.items():
                    if isinstance(val, (torch.Tensor if PYTORCH_AVAILABLE else type(None), np.ndarray)):
                        if PYTORCH_AVAILABLE and isinstance(val, torch.Tensor):
                            structure['data'][key] = {
                                'type': 'tensor',
                                'shape': tuple(val.shape),
                                'dtype': str(val.dtype),
                                'sample': val.flatten()[:5].tolist() if val.numel() > 0 else []
                            }
                        elif isinstance(val, np.ndarray):
                            structure['data'][key] = {
                                'type': 'array',
                                'shape': val.shape,
                                'dtype': str(val.dtype),
                                'sample': val.flatten()[:5].tolist() if val.size > 0 else []
                            }
                    else:
                        structure['data'][key] = {'type': type(val).__name__, 'value': str(val)[:100]}
            else:
                structure['type'] = type(data).__name__
                if hasattr(data, 'shape'):
                    structure['shape'] = data.shape
            
            all_structures.append(structure)
            print(f"\n{pkl_file.name}:")
            print(f"  Type: {structure['type']}")
            if 'keys' in structure:
                print(f"  Keys: {structure['keys']}")
                
        except Exception as e:
            print(f"Error loading {pkl_file.name}: {e}")
    
    # Find common structure
    if all_structures:
        common_keys = set.intersection(*[set(s.get('keys', [])) for s in all_structures if s.get('type') == 'dict'])
        print(f"\n\nCommon keys across files: {sorted(common_keys)}")
        
        return all_structures[0] if all_structures else None
    
    return None


def convert_to_product_a_format(data_dir: Path, output_csv: Path, label_csv: Optional[Path] = None):
    """Convert pickle files to CSV format suitable for Product A EKF processing."""
    pkl_files = sorted(data_dir.glob("*.pkl"))
    
    print(f"Converting {len(pkl_files)} pickle files to Product A format...")
    print("=" * 60)
    
    all_rows = []
    
    # Load labels if available
    labels = {}
    if label_csv and label_csv.exists():
        df_labels = pd.read_csv(label_csv)
        labels = dict(zip(df_labels['car'], df_labels['label']))
        print(f"Loaded {len(labels)} labels from {label_csv.name}")
    
    for idx, pkl_file in enumerate(pkl_files):
        try:
            data = load_pickle_file(pkl_file)
            
            # Extract car ID from filename (assuming it's the numeric part)
            car_id = pkl_file.stem
            
            # Try to extract time-series data
            if isinstance(data, dict):
                # Look for time-series arrays
                time_series_data = {}
                
                # Common keys that might contain time-series data
                potential_keys = {
                    'voltage': ['voltage', 'v', 'volt'],
                    'current': ['current', 'i', 'amp', 'ampere'],
                    'temperature': ['temp', 'temperature', 't'],
                    'soc': ['soc', 'state_of_charge', 'charge'],
                    'soh': ['soh', 'state_of_health', 'health'],
                    'time': ['time', 'timestamp', 't', 'duration'],
                    'mileage': ['mileage', 'distance', 'km'],
                    'cycle': ['cycle', 'cycle_idx']
                }
                
                for key, val in data.items():
                    key_lower = key.lower()
                    
                    # Check if this key matches any potential field
                    for field, keywords in potential_keys.items():
                        if any(kw in key_lower for kw in keywords):
                            if isinstance(val, (np.ndarray, list)) or (PYTORCH_AVAILABLE and isinstance(val, torch.Tensor)):
                                if PYTORCH_AVAILABLE and isinstance(val, torch.Tensor):
                                    val = val.numpy()
                                if isinstance(val, np.ndarray):
                                    time_series_data[field] = val
                                break
                
                # If we found time-series data, create rows
                if time_series_data:
                    # Get the length of the longest array
                    max_len = max(len(v) if hasattr(v, '__len__') else 1 for v in time_series_data.values())
                    
                    for i in range(max_len):
                        row = {'car_id': car_id, 'sample_idx': i}
                        
                        # Add label if available
                        if car_id in labels:
                            row['label'] = labels[car_id]
                        
                        # Add all time-series fields
                        for field, arr in time_series_data.items():
                            if i < len(arr):
                                row[field] = arr[i] if not isinstance(arr[i], (list, np.ndarray)) else arr[i].item()
                            else:
                                row[field] = None
                        
                        all_rows.append(row)
                else:
                    # If no time-series found, create a single row with all data
                    row = {'car_id': car_id}
                    if car_id in labels:
                        row['label'] = labels[car_id]
                    
                    for key, val in data.items():
                        if isinstance(val, (np.ndarray, list)) or (PYTORCH_AVAILABLE and isinstance(val, torch.Tensor)):
                            if PYTORCH_AVAILABLE and isinstance(val, torch.Tensor):
                                val = val.numpy()
                            if isinstance(val, np.ndarray) and val.size == 1:
                                row[key] = val.item()
                            elif isinstance(val, np.ndarray):
                                row[key] = str(val.shape)  # Store shape info
                            else:
                                row[key] = val[0] if len(val) > 0 else None
                        else:
                            row[key] = val
                    
                    all_rows.append(row)
            
            if (idx + 1) % 50 == 0:
                print(f"  Processed {idx + 1}/{len(pkl_files)} files...")
                
        except Exception as e:
            print(f"Error processing {pkl_file.name}: {e}")
            continue
    
    # Create DataFrame and save
    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_csv(output_csv, index=False)
        print(f"\n✅ Converted {len(all_rows)} rows to {output_csv}")
        print(f"   Columns: {list(df.columns)}")
        print(f"   Shape: {df.shape}")
        return df
    else:
        print("\n❌ No data extracted from pickle files")
        return None


if __name__ == "__main__":
    dataset_path = Path.home() / "Downloads" / "battery_dataset1.tar.gz"
    temp_dir = Path("/tmp/battery_dataset_analysis")
    
    # Extract if needed
    if not (temp_dir / "battery_dataset1").exists():
        import tarfile
        print("Extracting dataset...")
        with tarfile.open(dataset_path, 'r:gz') as tar:
            tar.extractall(temp_dir)
    
    data_dir = temp_dir / "battery_dataset1" / "data"
    label_csv = temp_dir / "battery_dataset1" / "label" / "label.csv"
    
    # First analyze structure
    print("Step 1: Analyzing pickle file structure...")
    structure = analyze_pickle_structure(data_dir, num_samples=10)
    
    # Then convert
    print("\n\nStep 2: Converting to Product A format...")
    output_csv = Path("/tmp/battery_dataset_converted.csv")
    df = convert_to_product_a_format(data_dir, output_csv, label_csv)
    
    if df is not None:
        print(f"\n✅ Conversion complete! Output saved to: {output_csv}")
        print(f"\nSample data:")
        print(df.head(10))

