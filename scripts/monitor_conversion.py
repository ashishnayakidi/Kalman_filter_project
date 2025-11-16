"""
Monitor battery dataset conversion progress and notify when complete.
"""
import time
import subprocess
from pathlib import Path
import sys


def check_conversion_status():
    """Check if conversion is still running."""
    # Check if process is running
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'convert_battery_dataset_full.py'],
            capture_output=True,
            text=True
        )
        is_running = result.returncode == 0
    except:
        is_running = False
    
    # Check output file
    output_file = Path(__file__).parent.parent / "data" / "processed" / "battery_dataset1_ekf.csv"
    file_exists = output_file.exists()
    file_size = output_file.stat().st_size if file_exists else 0
    
    # Check log file
    log_file = Path("/tmp/battery_conversion.log")
    log_exists = log_file.exists()
    
    # Get last few lines of log if available
    last_log_lines = []
    if log_exists:
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                last_log_lines = lines[-10:] if len(lines) > 10 else lines
        except:
            pass
    
    return {
        'is_running': is_running,
        'file_exists': file_exists,
        'file_size_mb': file_size / (1024 * 1024),
        'log_exists': log_exists,
        'last_log_lines': last_log_lines
    }


def monitor_until_complete(check_interval=30):
    """Monitor conversion until complete."""
    print("=" * 70)
    print("Monitoring Battery Dataset Conversion")
    print("=" * 70)
    print(f"Checking every {check_interval} seconds...\n")
    
    last_file_size = 0
    stable_count = 0
    
    while True:
        status = check_conversion_status()
        
        if status['file_exists']:
            file_size_mb = status['file_size_mb']
            size_change = file_size_mb - last_file_size
            
            print(f"[{time.strftime('%H:%M:%S')}] Status:")
            print(f"  Process running: {'Yes' if status['is_running'] else 'No'}")
            print(f"  Output file size: {file_size_mb:.1f} MB")
            if last_file_size > 0:
                print(f"  Size change: {size_change:+.1f} MB")
            
            # Check if file size is stable (conversion might be done)
            if abs(size_change) < 0.1:  # Less than 0.1 MB change
                stable_count += 1
                if stable_count >= 3:  # Stable for 3 checks
                    if not status['is_running']:
                        print("\n" + "=" * 70)
                        print("✅ CONVERSION COMPLETE!")
                        print("=" * 70)
                        print(f"Final file size: {file_size_mb:.1f} MB")
                        print(f"Output file: data/processed/battery_dataset1_ekf.csv")
                        print("\nYou can now run EKF processing:")
                        print("  python scripts/run_replay.py --csv-path data/processed/battery_dataset1_ekf.csv")
                        return True
            else:
                stable_count = 0
            
            last_file_size = file_size_mb
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Waiting for output file to be created...")
            if status['is_running']:
                print("  Process is running...")
            else:
                print("  ⚠️  Process not running - conversion may have failed")
                if status['last_log_lines']:
                    print("\n  Last log lines:")
                    for line in status['last_log_lines'][-5:]:
                        print(f"    {line.rstrip()}")
                return False
        
        if not status['is_running'] and status['file_exists']:
            # Process stopped but file exists - might be complete
            if stable_count >= 2:
                print("\n" + "=" * 70)
                print("✅ CONVERSION COMPLETE!")
                print("=" * 70)
                print(f"Final file size: {file_size_mb:.1f} MB")
                print(f"Output file: data/processed/battery_dataset1_ekf.csv")
                print("\nYou can now run EKF processing:")
                print("  python scripts/run_replay.py --csv-path data/processed/battery_dataset1_ekf.csv")
                return True
        
        print()  # Empty line for readability
        time.sleep(check_interval)


if __name__ == "__main__":
    try:
        monitor_until_complete(check_interval=30)
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
        sys.exit(0)


