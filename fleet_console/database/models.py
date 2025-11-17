"""Database models for fleet monitoring."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List
import json


@dataclass
class Vehicle:
    """Vehicle information."""
    vin: str
    model: str
    region: str
    registration_date: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'vin': self.vin,
            'model': self.model,
            'region': self.region,
            'registration_date': self.registration_date.isoformat() if isinstance(self.registration_date, datetime) else str(self.registration_date),
            'latitude': self.latitude,
            'longitude': self.longitude
        }


@dataclass
class BatteryState:
    """Battery state at a point in time."""
    vin: str
    timestamp: datetime
    soc: float
    soh: float
    temperature: float
    voltage: float
    current: float
    warranty_score: Optional[float] = None
    rul_days: Optional[float] = None
    degradation_rate: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'vin': self.vin,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            'soc': self.soc,
            'soh': self.soh,
            'temperature': self.temperature,
            'voltage': self.voltage,
            'current': self.current,
            'warranty_score': self.warranty_score,
            'rul_days': self.rul_days,
            'degradation_rate': self.degradation_rate
        }


@dataclass
class Alert:
    """Alert for a vehicle."""
    vin: str
    alert_type: str  # 'degradation', 'thermal', 'fast_charge', 'warranty'
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    created_at: datetime
    resolved: bool = False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'vin': self.vin,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'message': self.message,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            'resolved': self.resolved
        }


# In-memory storage (for POC - replace with database in production)
_vehicles: Dict[str, Vehicle] = {}
_battery_states: List[BatteryState] = []
_alerts: List[Alert] = []


def add_vehicle(vehicle: Vehicle):
    """Add or update a vehicle."""
    _vehicles[vehicle.vin] = vehicle


def get_vehicle(vin: str) -> Optional[Vehicle]:
    """Get vehicle by VIN."""
    return _vehicles.get(vin)


def get_all_vehicles() -> List[Vehicle]:
    """Get all vehicles."""
    return list(_vehicles.values())


def add_battery_state(state: BatteryState):
    """Add a battery state."""
    _battery_states.append(state)
    # Keep only last 10000 states per vehicle (for memory management)
    vin_states = [s for s in _battery_states if s.vin == state.vin]
    if len(vin_states) > 10000:
        _battery_states[:] = [s for s in _battery_states if s.vin != state.vin] + vin_states[-10000:]


def get_latest_battery_state(vin: str) -> Optional[BatteryState]:
    """Get latest battery state for a vehicle."""
    states = [s for s in _battery_states if s.vin == vin]
    if not states:
        return None
    return max(states, key=lambda s: s.timestamp)


def get_battery_states(vin: str, limit: int = 1000) -> List[BatteryState]:
    """Get recent battery states for a vehicle."""
    states = [s for s in _battery_states if s.vin == vin]
    states.sort(key=lambda s: s.timestamp, reverse=True)
    return states[:limit]


def get_all_latest_states() -> Dict[str, BatteryState]:
    """Get latest state for all vehicles."""
    result = {}
    for state in _battery_states:
        if state.vin not in result or state.timestamp > result[state.vin].timestamp:
            result[state.vin] = state
    return result


def add_alert(alert: Alert):
    """Add an alert."""
    _alerts.append(alert)


def get_alerts(vin: Optional[str] = None, severity: Optional[str] = None, resolved: bool = False) -> List[Alert]:
    """Get alerts, optionally filtered."""
    alerts = _alerts
    if vin:
        alerts = [a for a in alerts if a.vin == vin]
    if severity:
        alerts = [a for a in alerts if a.severity == severity]
    if not resolved:
        alerts = [a for a in alerts if not a.resolved]
    alerts.sort(key=lambda a: a.created_at, reverse=True)
    return alerts


def clear_all_data():
    """Clear all data (for testing)."""
    global _vehicles, _battery_states, _alerts
    _vehicles.clear()
    _battery_states.clear()
    _alerts.clear()


