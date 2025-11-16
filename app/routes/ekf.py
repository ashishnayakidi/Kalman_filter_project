"""EKF state management endpoints."""
from fastapi import APIRouter, Depends
from app.core.models import EKFStateResponse, TickRequest, TickResponse
from app.core.config import (
    Q_AH_INIT, R0_INIT, R1_INIT, C1_INIT, ETA_INIT, SOC_INIT,
    EKF_Q_SOC, EKF_Q_VRC, EKF_R_VOLT
)
from agent.ekf import BatteryEKF
import pandas as pd
from pathlib import Path

router = APIRouter()

# Global EKF instance (singleton)
_ekf_instance: BatteryEKF = None


def get_ekf() -> BatteryEKF:
    """Get or create global EKF instance."""
    global _ekf_instance
    if _ekf_instance is None:
        # Try to load OCV table if available
        ocv_table = None
        ocv_path = Path('ocv_tables/ocv_table.csv')
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


@router.post("/tick", response_model=TickResponse)
async def process_tick(request: TickRequest, ekf: BatteryEKF = Depends(get_ekf)):
    """Process a single tick through EKF."""
    result = ekf.step(
        I_A=request.I_A,
        V_V=request.V_V,
        T_C=request.T_C,
        dt_s=request.dt_s
    )
    
    # Score the tick
    from agent.scoring import score_tick
    score_tick(result)
    
    return TickResponse(**result)


@router.get("/state", response_model=EKFStateResponse)
async def get_state(ekf: BatteryEKF = Depends(get_ekf)):
    """Get current EKF state."""
    state = ekf.get_state()
    return EKFStateResponse(**state)


@router.post("/reset")
async def reset_ekf(soc_init: float = 1.0, ekf: BatteryEKF = Depends(get_ekf)):
    """Reset EKF to initial state."""
    ekf.reset(soc_init=soc_init)
    return {"status": "reset", "soc_init": soc_init}

