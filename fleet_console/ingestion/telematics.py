"""Telematics data ingestion API."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fleet_console.database.models import (
    Vehicle, BatteryState, Alert,
    add_vehicle, add_battery_state, add_alert
)
from typing import Dict
try:
    from agent.ekf import BatteryEKF
    from agent.scoring import get_scorer, score_tick
    from agent.ocv import derive_ocv_table
except ImportError:
    # Fallback if agent module not available
    BatteryEKF = None
    get_scorer = None
    score_tick = None

router = APIRouter()


class TelematicsData(BaseModel):
    """Telematics data from vehicle."""
    vin: str
    timestamp: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    voltage: float
    current: float
    temperature: float
    model: Optional[str] = None
    region: Optional[str] = None


class BatchTelematicsData(BaseModel):
    """Batch telematics data."""
    data: List[TelematicsData]


# EKF instances per vehicle
_ekf_instances: Dict[str, BatteryEKF] = {}


def get_or_create_ekf(vin: str):
    """Get or create EKF instance for a vehicle."""
    if BatteryEKF is None:
        raise HTTPException(status_code=500, detail="EKF module not available")
    
    if vin not in _ekf_instances:
        # Initialize with default parameters
        _ekf_instances[vin] = BatteryEKF(
            Q_Ah=2.0, R0=0.03, R1=0.01, C1=2000.0, eta=0.98,
            soc_init=1.0,
            Q_soc=1e-7, Q_vrc=1e-5, R_volt=2.5e-5,
            ocv_table=None  # Will derive if needed
        )
    return _ekf_instances[vin]


@router.post("/ingest")
async def ingest_telematics(data: TelematicsData):
    """
    Ingest single telematics data point.
    Processes through EKF and updates vehicle state.
    """
    try:
        # Parse timestamp
        timestamp = datetime.fromisoformat(data.timestamp.replace('Z', '+00:00'))
        
        # Update or create vehicle
        vehicle = Vehicle(
            vin=data.vin,
            model=data.model or 'Unknown',
            region=data.region or 'Unknown',
            registration_date=timestamp,
            latitude=data.latitude,
            longitude=data.longitude
        )
        add_vehicle(vehicle)
        
        # Process through EKF (if available)
        predictions = {}
        if BatteryEKF is not None and get_scorer is not None:
            try:
                ekf = get_or_create_ekf(data.vin)
                scorer = get_scorer()
                
                # EKF step
                ekf_out = ekf.step(
                    I_A=data.current,
                    V_V=data.voltage,
                    T_C=data.temperature,
                    dt_s=1.0  # Assume 1 second intervals
                )
                
                # Score
                ekf_out['I_A'] = data.current
                ekf_out['V_V'] = data.voltage
                ekf_out['temp_C'] = data.temperature
                if score_tick:
                    score_tick(ekf_out)
                
                # Get daily summary for predictions
                daily = scorer.daily_summary()
                predictions = daily.get('predictions', {})
                
                # Calculate SOH from EKF params
                params = ekf_out.get('params', {})
                soh = (params.get('Q_Ah', 2.0) / 2.0) * 100
            except Exception as e:
                # Fallback if EKF processing fails
                soh = 100.0  # Default
        else:
            # Fallback: estimate SOH from voltage (simple heuristic)
            soh = min(100, max(0, (data.voltage - 3.0) / 1.2 * 100))
            ekf_out = {}  # Empty dict for fallback
        
        # Create battery state
        battery_state = BatteryState(
            vin=data.vin,
            timestamp=timestamp,
            soc=(ekf_out.get('soc', data.voltage / 4.2) * 100) if BatteryEKF is not None else (data.voltage / 4.2 * 100),
            soh=soh,
            temperature=data.temperature,
            voltage=data.voltage,
            current=data.current,
            warranty_score=predictions.get('warranty_health_score'),
            rul_days=predictions.get('rul_days'),
            degradation_rate=abs(daily.get('dsoh_pct_per_week', 0.0) * 4.33)  # Per month
        )
        add_battery_state(battery_state)
        
        # Check for alerts
        if soh < 80:
            alert = Alert(
                vin=data.vin,
                alert_type='degradation',
                severity='critical' if soh < 70 else 'high',
                message=f'Battery SOH dropped to {soh:.1f}%',
                created_at=timestamp
            )
            add_alert(alert)
        
        if data.temperature > 50:
            alert = Alert(
                vin=data.vin,
                alert_type='thermal',
                severity='high',
                message=f'High temperature detected: {data.temperature:.1f}°C',
                created_at=timestamp
            )
            add_alert(alert)
        
        soc_value = ekf_out.get('soc', data.voltage / 4.2) if BatteryEKF is not None else (data.voltage / 4.2)
        
        return {
            'status': 'processed',
            'vin': data.vin,
            'soc': soc_value,
            'soh': soh
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing telematics data: {str(e)}")


@router.post("/ingest/batch")
async def ingest_batch_telematics(data: BatchTelematicsData):
    """Ingest multiple telematics data points."""
    results = []
    for item in data.data:
        try:
            result = await ingest_telematics(item)
            results.append(result)
        except Exception as e:
            results.append({'vin': item.vin, 'error': str(e)})
    
    return {
        'status': 'processed',
        'count': len(results),
        'results': results
    }


@router.get("/vehicles")
async def list_vehicles():
    """List all vehicles."""
    from fleet_console.database.models import get_all_vehicles
    vehicles = get_all_vehicles()
    return {'vehicles': [v.to_dict() for v in vehicles]}


@router.get("/vehicles/{vin}/state")
async def get_vehicle_state(vin: str):
    """Get latest state for a vehicle."""
    from fleet_console.database.models import get_latest_battery_state
    state = get_latest_battery_state(vin)
    if not state:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return state.to_dict()


@router.get("/alerts")
async def list_alerts(vin: Optional[str] = None, severity: Optional[str] = None):
    """List alerts."""
    from fleet_console.database.models import get_alerts
    alerts = get_alerts(vin=vin, severity=severity, resolved=False)
    return {'alerts': [a.to_dict() for a in alerts]}

