"""Analyze battery_dataset1.tar.gz to determine suitability for Product A."""
import tarfile
import csv
import sys
from pathlib import Path
from collections import Counter

def analyze_dataset(dataset_path: str):
    """Analyze the dataset and determine if it's suitable for Product A."""
    print("=" * 60)
    print("Battery Dataset Analysis for Product A")
    print("=" * 60)
    
    # Extract to temp location
    temp_dir = Path("/tmp/battery_dataset_analysis")
    temp_dir.mkdir(exist_ok=True)
    
    print(f"\n1. Extracting dataset from {dataset_path}...")
    try:
        with tarfile.open(dataset_path, 'r:gz') as tar:
            tar.extractall(temp_dir)
        print("   ✅ Extraction successful")
    except Exception as e:
        print(f"   ❌ Extraction failed: {e}")
        return
    
    # Find CSV files
    csv_files = list(temp_dir.rglob("*.csv"))
    print(f"\n2. Found {len(csv_files)} CSV file(s):")
    for csv_file in csv_files:
        print(f"   - {csv_file.relative_to(temp_dir)}")
    
    if not csv_files:
        print("\n❌ No CSV files found in dataset!")
        return
    
    # Analyze each CSV
    print("\n3. Analyzing CSV files:")
    all_data = {}
    
    for csv_file in csv_files:
        print(f"\n   Analyzing: {csv_file.name}")
        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            if not rows:
                print("   ⚠️  Empty file")
                continue
            
            print(f"   - Rows: {len(rows)}")
            print(f"   - Columns: {list(rows[0].keys())}")
            
            # Check for required fields for Product A
            required_fields = ['voltage', 'current', 'temperature', 'soc', 'soh', 'time', 'timestamp']
            found_fields = []
            for field in required_fields:
                for col in rows[0].keys():
                    if field.lower() in col.lower():
                        found_fields.append(col)
                        break
            
            print(f"   - Battery-related fields found: {found_fields if found_fields else 'None'}")
            
            # Show sample data
            print(f"   - Sample row: {dict(list(rows[0].items())[:5])}")
            
            all_data[csv_file.name] = {
                'rows': len(rows),
                'columns': list(rows[0].keys()),
                'sample': rows[0]
            }
            
        except Exception as e:
            print(f"   ❌ Error reading CSV: {e}")
    
    # Final assessment
    print("\n" + "=" * 60)
    print("Suitability Assessment for Product A")
    print("=" * 60)
    
    print("\nProduct A Requirements:")
    print("  ✓ Time-series voltage, current, temperature measurements")
    print("  ✓ SOC (State of Charge) tracking")
    print("  ✓ SOH (State of Health) tracking")
    print("  ✓ Charging/discharging cycle data")
    print("  ✓ Timestamp information")
    
    print("\nDataset Analysis:")
    has_timeseries = False
    has_battery_metrics = False
    
    for filename, data in all_data.items():
        cols = [c.lower() for c in data['columns']]
        
        # Check for time-series indicators
        time_fields = [c for c in cols if any(x in c for x in ['time', 'date', 'timestamp', 'cycle'])]
        if time_fields:
            has_timeseries = True
            print(f"  ✓ {filename}: Has time fields ({time_fields})")
        
        # Check for battery metrics
        battery_fields = [c for c in cols if any(x in c for x in ['voltage', 'current', 'temp', 'soc', 'soh', 'charge'])]
        if battery_fields:
            has_battery_metrics = True
            print(f"  ✓ {filename}: Has battery metrics ({battery_fields})")
        
        if not time_fields and not battery_fields:
            print(f"  ❌ {filename}: No time-series or battery metrics found")
            print(f"     Columns: {data['columns']}")
    
    print("\nConclusion:")
    if has_timeseries and has_battery_metrics:
        print("  ✅ Dataset appears suitable for Product A!")
        print("  → Can be processed through EKF and scoring system")
    elif has_battery_metrics:
        print("  ⚠️  Dataset has battery metrics but may lack time-series structure")
        print("  → May need preprocessing to add timestamps/cycles")
    else:
        print("  ❌ Dataset does not contain required battery monitoring data")
        print("  → This appears to be a classification dataset, not monitoring data")
        print("  → Cannot be directly used for Product A without additional data")
    
    return all_data


if __name__ == "__main__":
    dataset_path = Path.home() / "Downloads" / "battery_dataset1.tar.gz"
    
    if not dataset_path.exists():
        print(f"❌ Dataset not found at {dataset_path}")
        sys.exit(1)
    
    analyze_dataset(str(dataset_path))


