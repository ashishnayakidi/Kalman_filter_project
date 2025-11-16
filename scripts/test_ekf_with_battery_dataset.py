"""
Test EKF pipeline with converted battery dataset.

This script tests a sample of the converted dataset with the EKF pipeline
to verify compatibility and functionality.
"""
import pandas as pd
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.ekf import BatteryEKF
from agent.stream import tick_stream
from agent.scoring import get_scorer, score_tick
from agent.ocv import derive_ocv_table
import os
from dotenv import load_dotenv

load_dotenv()


def test_ekf_with_dataset(csv_path: Path, max_ticks: int = 1000):
    """
    Test EKF with converted battery dataset.
    
    Args:
        csv_path: Path to converted CSV file
        max_ticks: Maximum number of ticks to process (for testing)
    """
    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        print("   Run scripts/convert_battery_dataset_full.py first")
        return False
    
    print("=" * 70)
    print("Testing EKF with Battery Dataset")
    print("=" * 70)
    print(f"\nCSV file: {csv_path}")
    print(f"Max ticks to process: {max_ticks}\n")
    
    # Load and check CSV structure
    print("1. Loading CSV and checking structure...")
    df_sample = pd.read_csv(csv_path, nrows=100)
    
    required_cols = ['voltage_V', 'current_A', 'temp_C', 'dt_s', 'time_s']
    missing_cols = [col for col in required_cols if col not in df_sample.columns]
    
    if missing_cols:
        print(f"   ❌ Missing required columns: {missing_cols}")
        return False
    
    print(f"   ✅ Required columns present")
    print(f"   Columns: {list(df_sample.columns)}")
    print(f"   Sample data ranges:")
    print(f"     Voltage: {df_sample['voltage_V'].min():.2f} - {df_sample['voltage_V'].max():.2f} V")
    print(f"     Current: {df_sample['current_A'].min():.2f} - {df_sample['current_A'].max():.2f} A")
    print(f"     Temperature: {df_sample['temp_C'].min():.2f} - {df_sample['temp_C'].max():.2f} °C")
    
    # Derive OCV table from full dataset
    print("\n2. Deriving OCV table from dataset...")
    try:
        df_full = pd.read_csv(csv_path, nrows=10000)  # Sample for OCV derivation
        ocv_table = derive_ocv_table(df_full)
        print(f"   ✅ Derived OCV table with {len(ocv_table)} points")
    except Exception as e:
        print(f"   ⚠️  Could not derive OCV table: {e}")
        ocv_table = None
    
    # Initialize EKF
    print("\n3. Initializing EKF...")
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
    print(f"   ✅ EKF initialized")
    
    # Initialize scorer
    scorer = get_scorer()
    
    # Process ticks
    print(f"\n4. Processing ticks from {csv_path}...")
    results = []
    tick_count = 0
    last_cycle = -1
    errors = []
    
    try:
        for tick in tick_stream(str(csv_path)):
            if tick_count >= max_ticks:
                break
            
            if tick['cycle_idx'] != last_cycle:
                if last_cycle >= 0:
                    print(f"   Processed cycle {last_cycle}...")
                last_cycle = tick['cycle_idx']
            
            try:
                # EKF step
                ekf_out = ekf.step(
                    I_A=tick['current_A'],
                    V_V=tick['voltage_V'],
                    T_C=tick['temp_C'],
                    dt_s=tick['dt_s']
                )
                
                # Add tick metadata
                ekf_out['cycle_idx'] = tick['cycle_idx']
                ekf_out['cycle_type'] = tick.get('cycle_type', 'unknown')
                ekf_out['time_s'] = tick['time_s']
                ekf_out['I_A'] = tick['current_A']
                ekf_out['V_V'] = tick['voltage_V']
                
                # Score
                score_tick(ekf_out)
                
                results.append(ekf_out)
                tick_count += 1
                
                if tick_count % 100 == 0:
                    print(f"   Processed {tick_count} ticks...")
                    
            except Exception as e:
                errors.append(f"Tick {tick_count}: {str(e)}")
                if len(errors) <= 5:
                    print(f"   ⚠️  Error at tick {tick_count}: {e}")
                continue
        
        print(f"\n   ✅ Processed {tick_count} ticks successfully")
        
        if errors:
            print(f"   ⚠️  {len(errors)} errors encountered (first 5 shown above)")
        
    except Exception as e:
        print(f"   ❌ Error processing ticks: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    print("\n" + "=" * 70)
    print("Test Results Summary")
    print("=" * 70)
    
    if results:
        df_results = pd.DataFrame(results)
        
        print(f"\n✅ EKF processing successful!")
        print(f"   Total ticks processed: {len(results)}")
        print(f"   Unique cycles: {df_results['cycle_idx'].nunique()}")
        print(f"\n   SOC range: {df_results['soc'].min():.3f} - {df_results['soc'].max():.3f}")
        print(f"   Voltage prediction range: {df_results['v_pred'].min():.3f} - {df_results['v_pred'].max():.3f} V")
        print(f"   Residual range: {df_results['residual'].min():.6f} - {df_results['residual'].max():.6f} V")
        
        # Print daily summary
        daily = scorer.daily_summary()
        print(f"\n   Scoring summary:")
        print(f"     DCIR estimates: {len(daily.get('dcir_estimates', {}))}")
        print(f"     SOH estimates: {len(daily.get('soh_estimates', []))}")
        
        print(f"\n✅ EKF pipeline test PASSED!")
        return True
    else:
        print(f"\n❌ No results generated")
        return False


def main():
    """Main test function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test EKF with battery dataset')
    parser.add_argument('--csv-path', 
                       default='data/processed/battery_dataset1_ekf.csv',
                       help='Path to converted CSV file')
    parser.add_argument('--max-ticks', type=int, default=1000,
                       help='Maximum number of ticks to process (default: 1000)')
    
    args = parser.parse_args()
    
    csv_path = Path(args.csv_path)
    
    success = test_ekf_with_dataset(csv_path, args.max_ticks)
    
    if success:
        print(f"\n✅ Dataset is compatible with EKF pipeline!")
        print(f"   You can now process the full dataset with:")
        print(f"   python scripts/run_replay.py --csv-path {csv_path}")
    else:
        print(f"\n❌ Dataset compatibility issues found")
        sys.exit(1)


if __name__ == '__main__':
    main()

