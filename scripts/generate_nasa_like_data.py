"""Generate NASA-like synthetic battery data for testing."""
import pandas as pd
import numpy as np
from pathlib import Path


def generate_nasa_like_data(output_path: Path, num_cycles: int = 10, points_per_cycle: int = 500):
    """
    Generate synthetic NASA-like battery data.
    
    Args:
        output_path: Path to output CSV
        num_cycles: Number of charge/discharge cycles
        points_per_cycle: Data points per cycle
    """
    rows = []
    cycle_idx = 0
    
    # Initial capacity (degrades over time)
    initial_capacity = 2.0  # Ah
    capacity_degradation = 0.001  # per cycle
    
    for cycle_idx in range(num_cycles):
        # Cycle type alternates or random
        cycle_type = 'discharge' if cycle_idx % 2 == 0 else 'charge'
        
        # Capacity decreases over cycles
        capacity = initial_capacity * (1 - capacity_degradation * cycle_idx)
        
        # Time series for this cycle
        time_points = np.linspace(0, 3600, points_per_cycle)  # 1 hour cycle
        dt_s = np.diff(time_points, prepend=0)
        
        # SOC starts at 1.0 for discharge, 0.0 for charge
        if cycle_type == 'discharge':
            soc_start = 1.0
            current_base = -1.5  # Negative for discharge
        else:
            soc_start = 0.0
            current_base = 1.5  # Positive for charge
        
        # Generate realistic voltage/current profiles
        for i, t in enumerate(time_points):
            # SOC evolution
            soc = soc_start + (current_base / capacity) * (t / 3600)
            soc = np.clip(soc, 0.0, 1.0)
            
            # OCV based on SOC (simple model)
            ocv = 3.0 + 1.2 * soc
            
            # Current with some noise and variation
            current = current_base + np.random.randn() * 0.1
            # Add some current variation (pulses, etc.)
            if i % 50 == 0:
                current *= 1.2  # Simulate pulse
            
            # Voltage = OCV - I*R - RC effects
            R0 = 0.03
            voltage = ocv - current * R0 + np.random.randn() * 0.01
            
            # Temperature (varies slightly)
            temp = 25.0 + np.random.randn() * 2.0
            temp = np.clip(temp, 20.0, 35.0)
            
            rows.append({
                'cycle_idx': cycle_idx,
                'cycle_type': cycle_type,
                'time_s': float(t),
                'dt_s': float(dt_s[i]),
                'voltage_V': float(voltage),
                'current_A': float(current),
                'temp_C': float(temp),
                'capacity_Ah_cycle': float(capacity)
            })
        
        # Alternate cycle type
        cycle_type = 'charge' if cycle_type == 'discharge' else 'discharge'
    
    df = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    
    print(f"Generated {len(df)} rows across {num_cycles} cycles")
    print(f"Saved to: {output_path}")
    return df


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='data/processed/B0005_flat.csv')
    parser.add_argument('--cycles', type=int, default=10)
    parser.add_argument('--points', type=int, default=500)
    args = parser.parse_args()
    
    generate_nasa_like_data(Path(args.output), args.cycles, args.points)

