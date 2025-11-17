"""Fleet-level analytics and aggregations."""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from fleet_console.database.models import get_all_vehicles, get_all_latest_states, get_battery_states, BatteryState


def get_fleet_health_overview() -> Dict:
    """Get aggregate fleet health metrics."""
    vehicles = get_all_vehicles()
    latest_states = get_all_latest_states()
    
    if not vehicles:
        return {
            'total_vehicles': 0,
            'avg_soh': 0.0,
            'avg_degradation_rate': 0.0,
            'vehicles_at_risk': 0,
            'soh_distribution': {}
        }
    
    soh_values = []
    degradation_rates = []
    vehicles_at_risk = 0
    
    for vehicle in vehicles:
        state = latest_states.get(vehicle.vin)
        if state:
            soh_values.append(state.soh)
            if state.degradation_rate:
                degradation_rates.append(state.degradation_rate)
            if state.soh < 80 or (state.rul_days and state.rul_days < 90):
                vehicles_at_risk += 1
    
    # SOH distribution
    soh_distribution = {
        'excellent': sum(1 for soh in soh_values if soh >= 90),
        'good': sum(1 for soh in soh_values if 80 <= soh < 90),
        'fair': sum(1 for soh in soh_values if 70 <= soh < 80),
        'poor': sum(1 for soh in soh_values if soh < 70)
    }
    
    return {
        'total_vehicles': len(vehicles),
        'avg_soh': sum(soh_values) / len(soh_values) if soh_values else 0.0,
        'avg_degradation_rate': sum(degradation_rates) / len(degradation_rates) if degradation_rates else 0.0,
        'vehicles_at_risk': vehicles_at_risk,
        'soh_distribution': soh_distribution
    }


def get_regional_stats() -> Dict[str, Dict]:
    """Get statistics by region."""
    vehicles = get_all_vehicles()
    latest_states = get_all_latest_states()
    
    regional_stats = defaultdict(lambda: {'vehicles': 0, 'avg_soh': 0.0, 'soh_values': []})
    
    for vehicle in vehicles:
        state = latest_states.get(vehicle.vin)
        if state:
            regional_stats[vehicle.region]['vehicles'] += 1
            regional_stats[vehicle.region]['soh_values'].append(state.soh)
    
    # Calculate averages
    for region, stats in regional_stats.items():
        if stats['soh_values']:
            stats['avg_soh'] = sum(stats['soh_values']) / len(stats['soh_values'])
        del stats['soh_values']  # Remove raw values
    
    return dict(regional_stats)


def get_vehicles_at_risk(limit: int = 20) -> List[Dict]:
    """Get vehicles likely to hit 80% SOH soon, ranked by risk."""
    vehicles = get_all_vehicles()
    latest_states = get_all_latest_states()
    
    at_risk = []
    
    for vehicle in vehicles:
        state = latest_states.get(vehicle.vin)
        if not state:
            continue
        
        risk_score = 0.0
        time_to_80 = None
        
        # Calculate risk
        if state.soh < 80:
            risk_score = 100.0  # Already below 80
        elif state.soh < 90:
            risk_score = 70.0
        elif state.degradation_rate and state.degradation_rate > 0:
            # Estimate time to 80%
            days_to_80 = ((state.soh - 80) / state.degradation_rate) * 30 if state.degradation_rate > 0 else None
            if days_to_80 and days_to_80 < 180:  # Less than 6 months
                risk_score = 50.0 + (180 - days_to_80) / 180 * 50
                time_to_80 = days_to_80
        
        if risk_score > 0 or state.soh < 90:
            at_risk.append({
                'vin': vehicle.vin,
                'model': vehicle.model,
                'region': vehicle.region,
                'soh': state.soh,
                'degradation_rate': state.degradation_rate,
                'rul_days': state.rul_days,
                'risk_score': risk_score,
                'time_to_80_days': time_to_80
            })
    
    # Sort by risk score (highest first)
    at_risk.sort(key=lambda x: x['risk_score'], reverse=True)
    return at_risk[:limit]


def get_historical_trends(vin: Optional[str] = None, days: int = 90) -> Dict:
    """Get historical SOH trends."""
    vehicles = get_all_vehicles()
    latest_states = get_all_latest_states()
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    if vin:
        # Single vehicle
        states = get_battery_states(vin, limit=10000)
        states = [s for s in states if s.timestamp >= cutoff_date]
        states.sort(key=lambda s: s.timestamp)
        
        return {
            'vin': vin,
            'timestamps': [s.timestamp.isoformat() if isinstance(s.timestamp, datetime) else str(s.timestamp) for s in states],
            'soh_values': [s.soh for s in states]
        }
    else:
        # Fleet average
        daily_soh = defaultdict(lambda: [])
        
        for vehicle in vehicles:
            states = get_battery_states(vehicle.vin, limit=10000)
            states = [s for s in states if s.timestamp >= cutoff_date]
            
            for state in states:
                date_key = state.timestamp.date() if isinstance(state.timestamp, datetime) else datetime.fromisoformat(str(state.timestamp)).date()
                daily_soh[date_key].append(state.soh)
        
        # Calculate daily averages
        dates = sorted(daily_soh.keys())
        avg_soh = [sum(daily_soh[d]) / len(daily_soh[d]) for d in dates]
        
        return {
            'dates': [d.isoformat() if isinstance(d, datetime) else str(d) for d in dates],
            'avg_soh': avg_soh
        }


def get_usage_clusters() -> Dict:
    """Identify usage patterns and clusters."""
    vehicles = get_all_vehicles()
    latest_states = get_all_latest_states()
    
    clusters = {
        'high_fast_charge': [],
        'high_temp': [],
        'low_usage': [],
        'aggressive_driving': []
    }
    
    for vehicle in vehicles:
        state = latest_states.get(vehicle.vin)
        if not state:
            continue
        
        # Get recent states to analyze usage
        recent_states = get_battery_states(vehicle.vin, limit=1000)
        
        if not recent_states:
            continue
        
        # Analyze patterns
        avg_temp = sum(s.temperature for s in recent_states) / len(recent_states)
        max_current = max(abs(s.current) for s in recent_states)
        
        if avg_temp > 45:
            clusters['high_temp'].append({
                'vin': vehicle.vin,
                'model': vehicle.model,
                'avg_temp': avg_temp
            })
        
        if max_current > 50:  # High current indicates fast charging
            clusters['high_fast_charge'].append({
                'vin': vehicle.vin,
                'model': vehicle.model,
                'max_current': max_current
            })
        
        # Low usage: few state updates
        if len(recent_states) < 100:
            clusters['low_usage'].append({
                'vin': vehicle.vin,
                'model': vehicle.model,
                'state_count': len(recent_states)
            })
    
    return clusters


def predict_failures() -> List[Dict]:
    """Predict which vehicles will fail soon."""
    vehicles = get_all_vehicles()
    latest_states = get_all_latest_states()
    
    predictions = []
    
    for vehicle in vehicles:
        state = latest_states.get(vehicle.vin)
        if not state:
            continue
        
        # Simple failure prediction based on multiple factors
        failure_probability = 0.0
        
        # SOH below 80%
        if state.soh < 80:
            failure_probability += 0.5
        
        # Fast degradation
        if state.degradation_rate and state.degradation_rate > 1.0:  # >1% per month
            failure_probability += 0.3
        
        # Low RUL
        if state.rul_days and state.rul_days < 30:
            failure_probability += 0.2
        
        if failure_probability > 0.3:  # Threshold
            predictions.append({
                'vin': vehicle.vin,
                'model': vehicle.model,
                'region': vehicle.region,
                'soh': state.soh,
                'rul_days': state.rul_days,
                'failure_probability': min(1.0, failure_probability),
                'estimated_failure_date': (datetime.now() + timedelta(days=state.rul_days or 90)).isoformat() if state.rul_days else None
            })
    
    predictions.sort(key=lambda x: x['failure_probability'], reverse=True)
    return predictions


def get_lead_generation_candidates() -> List[Dict]:
    """Identify vehicles due for pack replacement or upgrade."""
    vehicles = get_all_vehicles()
    latest_states = get_all_latest_states()
    
    candidates = []
    
    for vehicle in vehicles:
        state = latest_states.get(vehicle.vin)
        if not state:
            continue
        
        # Criteria for lead generation
        is_candidate = False
        reason = []
        
        if state.soh < 80:
            is_candidate = True
            reason.append('SOH below 80%')
        
        if state.rul_days and state.rul_days < 90:
            is_candidate = True
            reason.append(f'RUL less than 90 days ({state.rul_days:.0f} days)')
        
        if state.warranty_score and state.warranty_score < 70:
            is_candidate = True
            reason.append(f'Low warranty score ({state.warranty_score:.0f}/100)')
        
        if is_candidate:
            candidates.append({
                'vin': vehicle.vin,
                'model': vehicle.model,
                'region': vehicle.region,
                'soh': state.soh,
                'rul_days': state.rul_days,
                'warranty_score': state.warranty_score,
                'reasons': reason,
                'priority': 'high' if state.soh < 75 else 'medium'
            })
    
    candidates.sort(key=lambda x: (x['soh'], x.get('rul_days', 999)), reverse=False)
    return candidates


