"""Core utilities for Streamlit frontend - shared state management."""
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import threading
import time
import pandas as pd

# Import backend components
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agent.ekf import BatteryEKF
from agent.scoring import get_scorer, score_tick
from lfm.runner import LocalLFM
from dotenv import load_dotenv

load_dotenv()

# Configuration
Q_AH_INIT = float(os.getenv('Q_AH_INIT', '2.0'))
R0_INIT = float(os.getenv('R0_INIT', '0.03'))
R1_INIT = float(os.getenv('R1_INIT', '0.01'))
C1_INIT = float(os.getenv('C1_INIT', '2000.0'))
ETA_INIT = float(os.getenv('ETA_INIT', '0.98'))
SOC_INIT = float(os.getenv('SOC_INIT', '1.0'))
EKF_Q_SOC = float(os.getenv('EKF_Q_SOC', '1e-7'))
EKF_Q_VRC = float(os.getenv('EKF_Q_VRC', '1e-5'))
EKF_R_VOLT = float(os.getenv('EKF_R_VOLT', '2.5e-5'))
MODEL_PATH = os.getenv('MODEL_PATH', 'models/LFM2-350M-Q4_K_M.gguf')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'sam860/lfm2:350m')
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')

# Global instances (shared across Streamlit sessions)
_ekf_instance: Optional[BatteryEKF] = None
_lfm_instance: Optional[LocalLFM] = None
_scorer = None
_last_fetch_time: Optional[datetime] = None
_fetch_lock = threading.Lock()
_fetch_interval_hours = 1.0
_initialized = False


def get_ekf() -> BatteryEKF:
    """Get or create EKF instance."""
    global _ekf_instance
    if _ekf_instance is None:
        ocv_table = None
        ocv_path = project_root / 'ocv_tables' / 'ocv_table.csv'
        if ocv_path.exists():
            try:
                ocv_table = pd.read_csv(ocv_path)
            except:
                pass
        
        _ekf_instance = BatteryEKF(
            Q_Ah=Q_AH_INIT,
            R0=R0_INIT,
            R1=R1_INIT,
            C1=C1_INIT,
            eta=ETA_INIT,
            soc_init=SOC_INIT,
            Q_soc=EKF_Q_SOC,
            Q_vrc=EKF_Q_VRC,
            R_volt=EKF_R_VOLT,
            ocv_table=ocv_table
        )
    return _ekf_instance


def get_lfm() -> Optional[LocalLFM]:
    """Get or create LFM instance (tries Ollama first, then local file)."""
    global _lfm_instance
    
    # Always try to initialize if None, or if current instance failed
    if _lfm_instance is None:
        # Try Ollama first
        try:
            import requests
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_found = any(m.get('name') == OLLAMA_MODEL for m in models)
                if model_found:
                    try:
                        _lfm_instance = LocalLFM(model_name=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)
                        print(f"✓ Using Ollama model: {OLLAMA_MODEL}")
                        return _lfm_instance
                    except Exception as e:
                        print(f"Warning: Failed to initialize Ollama model: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    available = [m.get('name') for m in models]
                    print(f"Warning: Ollama model '{OLLAMA_MODEL}' not found. Available: {available}")
            else:
                print(f"Warning: Ollama API returned status {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"Warning: Could not connect to Ollama at {OLLAMA_BASE_URL}. Is Ollama running?")
        except Exception as e:
            print(f"Warning: Ollama check failed: {e}")
        
        # Fallback to local GGUF file
        model_path = Path(MODEL_PATH)
        if not model_path.is_absolute():
            model_path = project_root / model_path
        if model_path.exists():
            try:
                _lfm_instance = LocalLFM(model_path=str(model_path))
                print(f"✓ Using local model file: {model_path}")
            except Exception as e:
                print(f"Warning: Failed to load local model: {e}")
                import traceback
                traceback.print_exc()
                return None
        else:
            print(f"Warning: Model not found at {model_path} and Ollama not available")
            return None
    
    return _lfm_instance


def get_scorer_instance():
    """Get scorer instance."""
    global _scorer
    if _scorer is None:
        _scorer = get_scorer()
    return _scorer


def _load_initial_data():
    """Load sample data if EKF is empty."""
    global _last_fetch_time
    try:
        ekf = get_ekf()
        if len(ekf.history) == 0:
            ekf_csv = project_root / 'data/processed/B0005_flat_ekf_timeseries.csv'
            if ekf_csv.exists():
                try:
                    df = pd.read_csv(ekf_csv)
                    if 'cycle_type' in df.columns:
                        discharge_df = df[df['cycle_type'] == 'discharge']
                        if len(discharge_df) > 0:
                            sample_df = discharge_df.sample(min(100, len(discharge_df)))
                        else:
                            sample_df = df.sample(min(100, len(df)))
                    else:
                        sample_df = df[df['soc'].between(0.1, 0.9)].sample(min(100, len(df[df['soc'].between(0.1, 0.9)])))
                        if len(sample_df) == 0:
                            sample_df = df.sample(min(100, len(df)))
                    
                    for _, row in sample_df.iterrows():
                        ekf.history.append({
                            'soc': float(row.get('soc', 0.5)),
                            'v_pred': float(row.get('v_pred', row.get('V_V', 3.7))),
                            'residual': float(row.get('residual', 0.0)),
                            'temp_C': float(row.get('temp_C', 25.0)),
                            'V_V': float(row.get('V_V', row.get('v_pred', 3.7)))
                        })
                    
                    scorer = get_scorer_instance()
                    discharge_df = df[df.get('cycle_type', '') == 'discharge'].copy() if 'cycle_type' in df.columns else df.copy()
                    
                    if len(discharge_df) > 0:
                        discharge_df['soc_pct'] = (discharge_df['soc'] * 100).round().astype(int)
                        dcir_candidates = discharge_df[
                            (discharge_df['soc_pct'].isin([8, 9, 10, 11, 12, 48, 49, 50, 51, 52, 78, 79, 80, 81, 82])) &
                            (abs(discharge_df['residual']) < 0.05)
                        ]
                        
                        if len(dcir_candidates) > 0:
                            sample_df = dcir_candidates.sample(min(200, len(dcir_candidates)))
                        else:
                            sample_df = discharge_df.sample(min(200, len(discharge_df)))
                        
                        processed_count = 0
                        for _, row in sample_df.iterrows():
                            try:
                                score_tick({
                                    'soc': float(row.get('soc', 0.5)),
                                    'residual': float(row.get('residual', 0.0)),
                                    'temp_C': float(row.get('temp_C', 25.0)),
                                    'params': {'Q_Ah': 2.0, 'R0': 0.03, 'R1': 0.01, 'C1': 2000.0, 'eta': 0.98},
                                    'I_A': float(row.get('I_A', row.get('current_A', -1.5))),
                                    'v_pred': float(row.get('v_pred', 3.7))
                                })
                                processed_count += 1
                            except:
                                pass
                        
                        print(f"✓ Populated scorer with {processed_count} data points")
                except Exception as e:
                    print(f"Could not load historical data: {e}")
        
        _last_fetch_time = datetime.now()
    except Exception as e:
        print(f"Error in _load_initial_data: {e}")


def fetch_and_process_data(force: bool = False) -> bool:
    """
    Fetch and process data:
    1. Check for .mat files in download folder or data/raw
    2. Flatten .mat files to CSV if found
    3. Process CSV through EKF
    4. Load processed data
    """
    global _last_fetch_time
    
    with _fetch_lock:
        now = datetime.now()
        if not force and _last_fetch_time is not None:
            time_since_fetch = (now - _last_fetch_time).total_seconds() / 3600
            if time_since_fetch < _fetch_interval_hours:
                return False
        
        try:
            # Step 1: Check for .mat files in download folder or data/raw
            download_folder = Path.home() / 'Downloads'
            raw_data_dir = project_root / 'data/raw'
            
            mat_file = None
            # Check download folder first
            for folder in [download_folder, raw_data_dir]:
                for mat_path in folder.glob('*.mat'):
                    if mat_path.name.startswith('B0005'):
                        mat_file = mat_path
                        print(f"Found .mat file: {mat_file}")
                        break
                if mat_file:
                    break
            
            # If .mat file found, flatten and process it
            if mat_file:
                print(f"Processing .mat file: {mat_file}")
                from scripts.nasa_load import flatten_nasa_mat
                from scripts.run_replay import main as run_replay_main
                import subprocess
                import sys
                
                # Flatten .mat to CSV
                flat_csv = project_root / 'data/processed/B0005_flat.csv'
                flat_csv.parent.mkdir(parents=True, exist_ok=True)
                
                print(f"Flattening {mat_file} to {flat_csv}...")
                df_flat = flatten_nasa_mat(mat_file, flat_csv)
                print(f"Flattened {len(df_flat)} rows to CSV")
                
                # Process through EKF (run replay script)
                print("Processing through EKF...")
                ekf_csv = project_root / 'data/processed/B0005_flat_ekf_timeseries.csv'
                
                # Import replay logic directly
                from agent.ekf import BatteryEKF
                from agent.stream import tick_stream
                from agent.scoring import get_scorer, score_tick
                from agent.ocv import derive_ocv_table
                
                # Derive OCV table
                ocv_table = derive_ocv_table(df_flat)
                print(f"Derived OCV table with {len(ocv_table)} points")
                
                # Initialize EKF
                ekf_replay = BatteryEKF(
                    Q_Ah=Q_AH_INIT, R0=R0_INIT, R1=R1_INIT, C1=C1_INIT, eta=ETA_INIT,
                    soc_init=SOC_INIT,
                    Q_soc=EKF_Q_SOC, Q_vrc=EKF_Q_VRC, R_volt=EKF_R_VOLT,
                    ocv_table=ocv_table
                )
                
                # Initialize scorer
                scorer_replay = get_scorer()
                
                # Process ticks (limit to avoid infinite processing)
                # For manual fetch, we'll process a sample to keep it fast
                MAX_TICKS_FOR_MANUAL_FETCH = 5000  # Limit for manual fetch
                
                results = []
                tick_count = 0
                print(f"Processing ticks (limited to {MAX_TICKS_FOR_MANUAL_FETCH} for manual fetch)...")
                
                for tick in tick_stream(str(flat_csv)):
                    if tick_count >= MAX_TICKS_FOR_MANUAL_FETCH:
                        print(f"  Reached limit of {MAX_TICKS_FOR_MANUAL_FETCH} ticks, stopping...")
                        break
                    
                    # EKF step
                    ekf_out = ekf_replay.step(
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
                    
                    if tick_count % 500 == 0:
                        print(f"  Processed {tick_count} ticks...")
                
                # Save results
                if results:
                    df_results = pd.DataFrame(results)
                    df_results.to_csv(ekf_csv, index=False)
                    print(f"Saved EKF timeseries to {ekf_csv} ({len(df_results)} rows)")
                else:
                    print("Warning: No ticks processed")
            
            # Step 2: Load processed CSV
            ekf = get_ekf()
            scorer = get_scorer_instance()
            ekf_csv = project_root / 'data/processed/B0005_flat_ekf_timeseries.csv'
            
            if not ekf_csv.exists():
                print(f"Warning: Processed CSV not found: {ekf_csv}")
                return False
            
            df = pd.read_csv(ekf_csv)
            
            if force:
                ekf.history = []
                scorer.dcir_history = {10: [], 50: [], 80: []}
                scorer.dcir_baseline = {10: None, 50: None, 80: None}
                scorer.soh_history = []
                scorer.residual_history.clear()
            
            if 'cycle_type' in df.columns:
                discharge_df = df[df['cycle_type'] == 'discharge'].copy()
                if len(discharge_df) > 0:
                    sample_df = discharge_df.sample(min(100, len(discharge_df)))
                else:
                    sample_df = df.sample(min(100, len(df)))
            else:
                sample_df = df[df['soc'].between(0.1, 0.9)].sample(min(100, len(df[df['soc'].between(0.1, 0.9)])))
                if len(sample_df) == 0:
                    sample_df = df.sample(min(100, len(df)))
            
            for _, row in sample_df.iterrows():
                ekf.history.append({
                    'soc': float(row.get('soc', 0.5)),
                    'v_pred': float(row.get('v_pred', row.get('V_V', 3.7))),
                    'residual': float(row.get('residual', 0.0)),
                    'temp_C': float(row.get('temp_C', 25.0)),
                    'V_V': float(row.get('V_V', row.get('v_pred', 3.7)))
                })
            
            discharge_df = df[df.get('cycle_type', '') == 'discharge'].copy() if 'cycle_type' in df.columns else df.copy()
            if len(discharge_df) > 0:
                discharge_df['soc_pct'] = (discharge_df['soc'] * 100).round().astype(int)
                dcir_candidates = discharge_df[
                    (discharge_df['soc_pct'].isin([8, 9, 10, 11, 12, 48, 49, 50, 51, 52, 78, 79, 80, 81, 82])) &
                    (abs(discharge_df['residual']) < 0.05)
                ]
                
                if len(dcir_candidates) > 0:
                    sample_df = dcir_candidates.sample(min(200, len(dcir_candidates)))
                else:
                    sample_df = discharge_df.sample(min(200, len(discharge_df)))
                
                processed_count = 0
                for _, row in sample_df.iterrows():
                    try:
                        score_tick({
                            'soc': float(row.get('soc', 0.5)),
                            'residual': float(row.get('residual', 0.0)),
                            'temp_C': float(row.get('temp_C', 25.0)),
                            'params': {'Q_Ah': 2.0, 'R0': 0.03, 'R1': 0.01, 'C1': 2000.0, 'eta': 0.98},
                            'I_A': float(row.get('I_A', row.get('current_A', -1.5))),
                            'v_pred': float(row.get('v_pred', 3.7))
                        })
                        processed_count += 1
                    except:
                        pass
            
            _last_fetch_time = now
            print(f"Data fetch completed at {now}")
            return True
        except Exception as e:
            print(f"Error fetching data: {e}")
            import traceback
            traceback.print_exc()
            return False


def get_fetch_status():
    """Get data fetch status."""
    now = datetime.now()
    time_since_fetch = None
    next_fetch_in = None
    
    if _last_fetch_time:
        time_since_fetch = (now - _last_fetch_time).total_seconds() / 3600
        next_fetch_in = max(0, _fetch_interval_hours - time_since_fetch)
    
    return {
        'last_fetch_time': _last_fetch_time.isoformat() if _last_fetch_time else None,
        'time_since_fetch_hours': time_since_fetch,
        'next_fetch_in_hours': next_fetch_in,
        'fetch_interval_hours': _fetch_interval_hours
    }


def reset_lfm_instance():
    """Reset LFM instance (useful for debugging or re-initialization)."""
    global _lfm_instance
    _lfm_instance = None


def _start_auto_fetch_thread():
    """Start background thread for automatic hourly fetching."""
    def auto_fetch_loop():
        while True:
            try:
                time.sleep(3600)  # Wait 1 hour
                print("Auto-fetch: Checking for new data...")
                fetch_and_process_data(force=False)
            except Exception as e:
                print(f"Error in auto-fetch thread: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    thread = threading.Thread(target=auto_fetch_loop, daemon=True)
    thread.start()
    print("Started automatic hourly fetch thread")


def initialize_app():
    """Initialize the app (load data, etc.)."""
    global _initialized
    if not _initialized:
        _load_initial_data()
        # Try to initialize LFM early
        try:
            get_lfm()
        except Exception as e:
            print(f"Note: LFM initialization deferred: {e}")
        # Start automatic hourly fetching
        _start_auto_fetch_thread()
        _initialized = True

