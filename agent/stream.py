"""CSV tick stream generator."""
import pandas as pd
from typing import Iterator, Dict, Optional, Tuple


def tick_stream(csv_path: str, 
                use_types: Tuple[str, ...] = ('discharge', 'charge'),
                cycle_start: Optional[int] = None,
                cycle_end: Optional[int] = None) -> Iterator[Dict]:
    """
    Stream ticks from processed CSV.
    
    Args:
        csv_path: Path to processed CSV
        use_types: Cycle types to include
        cycle_start: Optional starting cycle index
        cycle_end: Optional ending cycle index
    
    Yields:
        Dictionary with tick data: {cycle_idx, cycle_type, time_s, dt_s, 
                                    voltage_V, current_A, temp_C, capacity_Ah_cycle}
    """
    df = pd.read_csv(csv_path)
    
    # Filter by cycle type
    if 'cycle_type' in df.columns:
        df = df[df['cycle_type'].isin(use_types)]
    
    # Filter by cycle range
    if cycle_start is not None and 'cycle_idx' in df.columns:
        df = df[df['cycle_idx'] >= cycle_start]
    if cycle_end is not None and 'cycle_idx' in df.columns:
        df = df[df['cycle_idx'] <= cycle_end]
    
    # Sort by time
    if 'time_s' in df.columns:
        df = df.sort_values('time_s')
    
    for _, row in df.iterrows():
        tick = {
            'cycle_idx': int(row.get('cycle_idx', 0)),
            'cycle_type': str(row.get('cycle_type', 'unknown')),
            'time_s': float(row.get('time_s', 0.0)),
            'dt_s': float(row.get('dt_s', 1.0)),
            'voltage_V': float(row.get('voltage_V', 0.0)),
            'current_A': float(row.get('current_A', 0.0)),
            'temp_C': float(row.get('temp_C', 25.0)),
            'capacity_Ah_cycle': float(row.get('capacity_Ah_cycle', 0.0))
        }
        yield tick

