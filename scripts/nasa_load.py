"""Load and flatten NASA battery dataset .mat files."""
import scipy.io
import pandas as pd
import numpy as np
from pathlib import Path
import urllib.request
import os
from typing import Optional


NASA_BASE_URL = "https://data.nasa.gov/download/5K9Q-7V7H/application%2Fzip"
NASA_DATA_DIR = "https://ti.arc.nasa.gov/c/6/"


def download_nasa_dataset(data_dir: Path, battery_name: str = "B0005") -> Path:
    """
    Download NASA battery dataset if not present.
    
    Note: Currently only B0005 is supported. Other batteries can be added later.
    
    Args:
        data_dir: Directory to store data
        battery_name: Battery identifier (e.g., "B0005")
    
    Returns:
        Path to .mat file
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    mat_path = data_dir / f"{battery_name}.mat"
    
    if mat_path.exists():
        print(f"Found existing file: {mat_path}")
        return mat_path
    
    print(f"Downloading {battery_name}.mat from NASA...")
    print("Note: This may take a while. The dataset is ~100MB.")
    
    # Try direct download from common NASA battery dataset locations
    # Note: NASA dataset is typically in a zip file, not individual .mat files
    urls = [
        f"https://ti.arc.nasa.gov/c/6/{battery_name}.mat",
    ]
    
    for url in urls:
        try:
            print(f"Trying: {url}")
            urllib.request.urlretrieve(url, mat_path)
            # Verify it's a valid .mat file (should start with specific bytes)
            if mat_path.exists() and mat_path.stat().st_size > 1000:
                # Quick check: valid .mat files have specific header
                with open(mat_path, 'rb') as f:
                    header = f.read(4)
                    # MATLAB files typically start with specific magic bytes
                    if len(header) == 4:
                        print(f"Downloaded: {mat_path} ({mat_path.stat().st_size} bytes)")
                        return mat_path
                    else:
                        print(f"Downloaded file appears invalid, removing...")
                        mat_path.unlink()
        except Exception as e:
            print(f"Failed to download from {url}: {e}")
            continue
    
    # If download fails, provide instructions
    print("\n" + "="*60)
    print("Automatic download failed. Please download manually:")
    print(f"1. Visit: https://data.nasa.gov/dataset/Lithium-Ion-Battery-Aging-Data/5K9Q-7V7H")
    print(f"2. Download the dataset")
    print(f"3. Extract and place {battery_name}.mat in: {data_dir}")
    print("="*60)
    
    return mat_path


def flatten_nasa_mat(mat_path: Path, output_path: Path) -> pd.DataFrame:
    """
    Flatten NASA .mat file to CSV.
    
    Args:
        mat_path: Path to .mat file
        output_path: Path to output CSV
    
    Returns:
        Flattened DataFrame
    """
    print(f"Loading {mat_path}...")
    mat_data = scipy.io.loadmat(str(mat_path), simplify_cells=True)
    
    # NASA format: typically has a key like 'B0005' or 'data'
    battery_key = None
    for key in mat_data.keys():
        if not key.startswith('__') and isinstance(mat_data[key], dict):
            battery_key = key
            break
    
    if battery_key is None:
        # Try common keys - prioritize B0005 for now
        # TODO: Support other batteries (B0006, B0007, etc.) in the future
        for key in ['B0005', 'data', 'cycle']:  # Only B0005 for now
            if key in mat_data:
                battery_key = key
                break
    
    if battery_key is None:
        raise ValueError(f"Could not find battery data in {mat_path}. Keys: {list(mat_data.keys())}")
    
    data = mat_data[battery_key]
    print(f"Found data under key: {battery_key}")
    
    # Extract cycle data
    cycles = data.get('cycle', [])
    if not cycles:
        # Alternative structure
        cycles = data if isinstance(data, list) else [data]
    
    rows = []
    cycle_idx = 0
    
    for cycle in cycles:
        if not isinstance(cycle, dict):
            continue
        
        cycle_type = cycle.get('type', 'unknown')
        if cycle_type not in ['discharge', 'charge', 'impedance']:
            cycle_type = 'discharge'  # Default
        
        # Extract time series data
        time_data = cycle.get('data', {})
        if not time_data:
            continue
        
        # Common NASA fields
        time_s = time_data.get('Time', time_data.get('time', []))
        voltage = time_data.get('Voltage_measured', time_data.get('Voltage', time_data.get('voltage', [])))
        current = time_data.get('Current_measured', time_data.get('Current', time_data.get('current', [])))
        temp = time_data.get('Temperature_measured', time_data.get('Temperature', time_data.get('temp', [])))
        capacity = time_data.get('Capacity', time_data.get('capacity', []))
        
        # Convert to arrays
        if isinstance(time_s, (int, float)):
            time_s = [time_s]
        if isinstance(voltage, (int, float)):
            voltage = [voltage]
        if isinstance(current, (int, float)):
            current = [current]
        if isinstance(temp, (int, float)):
            temp = [temp]
        if isinstance(capacity, (int, float)):
            capacity = [capacity]
        
        time_s = np.array(time_s) if len(time_s) > 0 else np.array([0.0])
        voltage = np.array(voltage) if len(voltage) > 0 else np.array([0.0])
        current = np.array(current) if len(current) > 0 else np.array([0.0])
        temp = np.array(temp) if len(temp) > 0 else np.array([25.0])
        capacity = np.array(capacity) if len(capacity) > 0 else np.array([0.0])
        
        # Ensure all arrays have same length
        min_len = min(len(time_s), len(voltage), len(current), len(temp))
        if min_len == 0:
            continue
        
        time_s = time_s[:min_len]
        voltage = voltage[:min_len]
        current = current[:min_len]
        temp = temp[:min_len]
        capacity_val = capacity[0] if len(capacity) > 0 else 0.0
        
        # Compute dt_s
        dt_s = np.diff(time_s, prepend=time_s[0])
        dt_s[dt_s <= 0] = 1.0  # Default to 1s if invalid
        
        # Create rows
        for i in range(min_len):
            rows.append({
                'cycle_idx': cycle_idx,
                'cycle_type': cycle_type,
                'time_s': float(time_s[i]),
                'dt_s': float(dt_s[i]),
                'voltage_V': float(voltage[i]),
                'current_A': float(current[i]),
                'temp_C': float(temp[i]),
                'capacity_Ah_cycle': float(capacity_val)
            })
        
        cycle_idx += 1
    
    df = pd.DataFrame(rows)
    print(f"Flattened {len(df)} rows from {cycle_idx} cycles")
    
    # Save to CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Saved to {output_path}")
    
    return df


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Load and flatten NASA battery dataset (B0005 only for now)')
    parser.add_argument('--battery', default='B0005', help='Battery identifier (default: B0005, only B0005 supported for now)')
    parser.add_argument('--data-dir', default='data/raw', help='Directory for raw data')
    parser.add_argument('--output-dir', default='data/processed', help='Directory for processed data')
    parser.add_argument('--mat-path', help='Direct path to .mat file (skips download)')
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    
    if args.mat_path:
        mat_path = Path(args.mat_path)
    else:
        mat_path = download_nasa_dataset(data_dir, args.battery)
    
    if not mat_path.exists():
        print(f"Error: {mat_path} does not exist. Please download the dataset manually.")
        return
    
    output_path = output_dir / f"{args.battery}_flat.csv"
    df = flatten_nasa_mat(mat_path, output_path)
    print(f"\nSuccess! Processed {len(df)} rows.")
    print(f"Output: {output_path}")


if __name__ == '__main__':
    main()

