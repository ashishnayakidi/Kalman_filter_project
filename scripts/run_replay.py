"""Replay processed CSV through EKF and generate outputs."""
import pandas as pd
import json
from pathlib import Path
import sys
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.ekf import BatteryEKF
from agent.stream import tick_stream
from agent.scoring import get_scorer, score_tick
from agent.ocv import derive_ocv_table
import os
from dotenv import load_dotenv

load_dotenv()


def main():
    """Main replay function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Replay CSV through EKF')
    parser.add_argument('--csv-path', default='data/processed/B0005_flat.csv',
                       help='Path to processed CSV (default: B0005_flat.csv - only B0005 supported for now)')
    parser.add_argument('--output-path', default=None,
                       help='Output path for EKF timeseries (default: auto)')
    parser.add_argument('--max-cycles', type=int, default=None,
                       help='Maximum number of cycles to process')
    
    args = parser.parse_args()
    
    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"Error: {csv_path} does not exist.")
        print("Run: python scripts/nasa_load.py first")
        return
    
    # Load and derive OCV table
    print("Loading CSV and deriving OCV table...")
    df = pd.read_csv(csv_path)
    ocv_table = derive_ocv_table(df)
    print(f"Derived OCV table with {len(ocv_table)} points")
    
    # Initialize EKF from environment or defaults
    Q_Ah = float(os.getenv('Q_AH_INIT', '2.0'))
    R0 = float(os.getenv('R0_INIT', '0.03'))
    R1 = float(os.getenv('R1_INIT', '0.01'))
    C1 = float(os.getenv('C1_INIT', '2000.0'))
    eta = float(os.getenv('ETA_INIT', '0.98'))
    soc_init = float(os.getenv('SOC_INIT', '1.0'))
    Q_soc = float(os.getenv('EKF_Q_SOC', '1e-7'))
    Q_vrc = float(os.getenv('EKF_Q_VRC', '1e-5'))
    R_volt = float(os.getenv('EKF_R_VOLT', '2.5e-5'))
    
    ekf = BatteryEKF(
        Q_Ah=Q_Ah, R0=R0, R1=R1, C1=C1, eta=eta,
        soc_init=soc_init,
        Q_soc=Q_soc, Q_vrc=Q_vrc, R_volt=R_volt,
        ocv_table=ocv_table
    )
    
    # Initialize scorer
    scorer = get_scorer()
    
    # Process ticks
    print(f"Processing ticks from {csv_path}...")
    results = []
    tick_count = 0
    last_cycle = -1
    
    for tick in tick_stream(str(csv_path)):
        if args.max_cycles and tick['cycle_idx'] > args.max_cycles:
            break
        
        if tick['cycle_idx'] != last_cycle:
            print(f"Processing cycle {tick['cycle_idx']}...")
            last_cycle = tick['cycle_idx']
        
        # EKF step
        ekf_out = ekf.step(
            I_A=tick['current_A'],
            V_V=tick['voltage_V'],
            T_C=tick['temp_C'],
            dt_s=tick['dt_s']
        )
        
        # Add tick metadata
        ekf_out['cycle_idx'] = tick['cycle_idx']
        ekf_out['cycle_type'] = tick['cycle_type']
        ekf_out['time_s'] = tick['time_s']
        ekf_out['I_A'] = tick['current_A']
        ekf_out['V_V'] = tick['voltage_V']
        
        # Score
        score_tick(ekf_out)
        
        results.append(ekf_out)
        tick_count += 1
        
        if tick_count % 1000 == 0:
            print(f"  Processed {tick_count} ticks...")
    
    print(f"\nProcessed {tick_count} ticks total")
    
    # Save results
    if args.output_path:
        output_path = Path(args.output_path)
    else:
        output_path = Path(args.csv_path).parent / f"{Path(args.csv_path).stem}_ekf_timeseries.csv"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to DataFrame
    df_results = pd.DataFrame(results)
    df_results.to_csv(output_path, index=False)
    print(f"Saved EKF timeseries to {output_path}")
    
    # Print daily summary
    daily = scorer.daily_summary()
    print("\n" + "="*60)
    print("Daily Summary:")
    print("="*60)
    print(json.dumps(daily, indent=2))
    print("="*60)


if __name__ == '__main__':
    main()

