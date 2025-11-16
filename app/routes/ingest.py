"""Data ingestion endpoints (replay)."""
from fastapi import APIRouter, HTTPException, Depends
from app.core.models import ReplayRequest, TickResponse
from agent.ekf import BatteryEKF
from agent.stream import tick_stream
from agent.scoring import score_tick
from agent.ocv import derive_ocv_table
from app.routes.ekf import get_ekf
import pandas as pd
from pathlib import Path

router = APIRouter()


@router.post("/replay")
async def replay_csv(request: ReplayRequest, ekf: BatteryEKF = Depends(get_ekf)):
    """
    Replay a CSV file through EKF.
    
    This processes all ticks in the CSV and returns the final state.
    """
    csv_path = Path(request.csv_path)
    
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV file not found: {csv_path}")
    
    # Load and derive OCV table if needed
    df = pd.read_csv(csv_path)
    ocv_table = derive_ocv_table(df)
    ekf.ocv_table = ocv_table
    
    # Process ticks
    results = []
    tick_count = 0
    
    try:
        for tick in tick_stream(str(csv_path)):
            ekf_out = ekf.step(
                I_A=tick['current_A'],
                V_V=tick['voltage_V'],
                T_C=tick['temp_C'],
                dt_s=tick['dt_s']
            )
            
            ekf_out['cycle_idx'] = tick['cycle_idx']
            ekf_out['cycle_type'] = tick['cycle_type']
            ekf_out['time_s'] = tick['time_s']
            
            score_tick(ekf_out)
            results.append(ekf_out)
            tick_count += 1
            
            if tick_count % 1000 == 0:
                print(f"Processed {tick_count} ticks...")
        
        # Save results
        output_path = csv_path.parent / f"{csv_path.stem}_ekf_timeseries.csv"
        df_results = pd.DataFrame(results)
        df_results.to_csv(output_path, index=False)
        
        return {
            "status": "completed",
            "tick_count": tick_count,
            "final_state": ekf.get_state(),
            "output_path": str(output_path)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during replay: {str(e)}")

