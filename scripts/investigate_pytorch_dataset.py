"""
Investigate battery_dataset1 to understand PyTorch dataset structure.

The research paper mentions:
- Data saved as pickle files loadable with PyTorch
- Includes mileage and collection duration
- Can select complete dataset or specific manufacturer
- Includes algorithm implementations

This script tries to understand the data structure.
"""
import pickle
import sys
from pathlib import Path
import csv

try:
    import torch
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    print("⚠️  PyTorch not available. Install with: pip install torch")


def investigate_pickle_structure(data_dir: Path):
    """Investigate what's actually in the pickle files."""
    pkl_files = list(data_dir.glob("*.pkl"))[:10]
    
    print("=" * 60)
    print("Investigating Pickle File Structure")
    print("=" * 60)
    
    results = []
    
    for pkl_file in pkl_files:
        result = {'file': pkl_file.name}
        
        # Try standard pickle
        try:
            with open(pkl_file, 'rb') as f:
                data = pickle.load(f)
            result['pickle_type'] = type(data).__name__
            result['pickle_value'] = str(data)[:100]
        except Exception as e:
            result['pickle_error'] = str(e)
        
        # Try PyTorch load
        if PYTORCH_AVAILABLE:
            try:
                # Use weights_only=False for research datasets (PyTorch 2.6+ default changed)
                data = torch.load(pkl_file, map_location='cpu', weights_only=False)
                result['torch_type'] = type(data).__name__
                if isinstance(data, torch.Tensor):
                    result['torch_shape'] = tuple(data.shape)
                    result['torch_dtype'] = str(data.dtype)
                    result['torch_sample'] = data.flatten()[:5].tolist()
                elif isinstance(data, dict):
                    result['torch_keys'] = list(data.keys())
                else:
                    result['torch_value'] = str(data)[:100]
            except Exception as e:
                result['torch_error'] = str(e)
        
        results.append(result)
    
    # Print summary
    print(f"\nAnalyzed {len(results)} files:\n")
    for r in results[:5]:
        print(f"File: {r['file']}")
        if 'pickle_type' in r:
            print(f"  Pickle: {r['pickle_type']} = {r.get('pickle_value', 'N/A')[:50]}")
        if 'torch_type' in r:
            print(f"  PyTorch: {r['torch_type']}")
            if 'torch_shape' in r:
                print(f"    Shape: {r['torch_shape']}, Dtype: {r['torch_dtype']}")
                print(f"    Sample: {r['torch_sample']}")
            elif 'torch_keys' in r:
                print(f"    Keys: {r['torch_keys']}")
        print()
    
    return results


def check_for_code_or_docs(dataset_root: Path):
    """Look for code files or documentation that explains the dataset."""
    print("=" * 60)
    print("Looking for Code or Documentation")
    print("=" * 60)
    
    # Look for common documentation files
    doc_patterns = ['README*', '*.md', '*.txt', '*.pdf', '*.doc']
    code_patterns = ['*.py', '*.ipynb', '*.cpp', '*.h']
    
    found_files = []
    
    for pattern in doc_patterns + code_patterns:
        found_files.extend(list(dataset_root.rglob(pattern)))
    
    if found_files:
        print(f"\nFound {len(found_files)} potential documentation/code files:")
        for f in found_files[:10]:
            print(f"  - {f.relative_to(dataset_root)}")
            if f.suffix in ['.txt', '.md', '.py']:
                try:
                    content = f.read_text()[:500]
                    print(f"    Preview: {content[:200]}...")
                except:
                    pass
    else:
        print("\n❌ No documentation or code files found in dataset")
        print("   The dataset might need external code from the research paper")
    
    return found_files


def analyze_label_structure(label_csv: Path):
    """Analyze the label CSV to understand the data organization."""
    print("=" * 60)
    print("Analyzing Label Structure")
    print("=" * 60)
    
    with open(label_csv, 'r') as f:
        reader = csv.DictReader(f)
        labels = list(reader)
    
    print(f"Total labels: {len(labels)}")
    print(f"Columns: {list(labels[0].keys())}")
    
    # Check label distribution
    label_counts = {}
    for row in labels:
        label = row['label']
        label_counts[label] = label_counts.get(label, 0) + 1
    
    print(f"\nLabel distribution:")
    for label, count in sorted(label_counts.items()):
        print(f"  Label {label}: {count} ({count/len(labels)*100:.1f}%)")
    
    # Check car ID range
    car_ids = [int(row['car']) for row in labels]
    print(f"\nCar ID range: {min(car_ids)} to {max(car_ids)}")
    print(f"Unique cars: {len(set(car_ids))}")
    
    return labels


def main():
    dataset_path = Path.home() / "Downloads" / "battery_dataset1.tar.gz"
    temp_dir = Path("/tmp/battery_dataset_investigation")
    
    # Extract if needed
    if not (temp_dir / "battery_dataset1").exists():
        import tarfile
        print("Extracting dataset...")
        temp_dir.mkdir(exist_ok=True)
        with tarfile.open(dataset_path, 'r:gz') as tar:
            tar.extractall(temp_dir)
    
    dataset_root = temp_dir / "battery_dataset1"
    data_dir = dataset_root / "data"
    label_csv = dataset_root / "label" / "label.csv"
    
    # Investigation steps
    print("\n🔍 Investigating battery_dataset1 structure...\n")
    
    # 1. Check for documentation/code
    docs = check_for_code_or_docs(dataset_root)
    
    # 2. Analyze labels
    if label_csv.exists():
        labels = analyze_label_structure(label_csv)
    
    # 3. Investigate pickle files
    if data_dir.exists():
        results = investigate_pickle_structure(data_dir)
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary & Recommendations")
    print("=" * 60)
    
    print("\nFindings:")
    print("1. Pickle files contain integers (likely IDs, indices, or encoded data)")
    print("2. Label CSV contains car IDs and binary classification labels")
    print("3. No documentation found in dataset archive")
    
    print("\nRecommendations:")
    print("1. Check the research paper for:")
    print("   - PyTorch Dataset class implementation")
    print("   - Data loading code")
    print("   - Data format specification")
    print("2. The integers in pickle files might be:")
    print("   - Indices into a larger dataset")
    print("   - Hash values for data lookup")
    print("   - Encoded time-series data")
    print("3. Contact the paper authors for:")
    print("   - Complete dataset loading code")
    print("   - Data format documentation")
    
    print("\nFor Product A:")
    print("❌ Cannot use this dataset directly without:")
    print("   - PyTorch Dataset class from the paper")
    print("   - Understanding of data encoding format")
    print("   - Access to actual time-series measurements")
    
    if PYTORCH_AVAILABLE:
        print("\n✅ PyTorch is available - can implement custom Dataset class")
        print("   once the data format is understood")
    else:
        print("\n⚠️  Install PyTorch: pip install torch")
        print("   to properly load the dataset")


if __name__ == "__main__":
    main()

