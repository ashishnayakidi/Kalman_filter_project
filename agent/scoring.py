"""Battery health scoring: DCIR, stress, drift detection."""
import numpy as np
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from collections import deque
from datetime import datetime, timedelta


class BatteryScorer:
    """Tracks battery health metrics and computes scores."""
    
    def __init__(self, thresholds_path: Optional[str] = None):
        """
        Initialize scorer.
        
        Args:
            thresholds_path: Path to thresholds.yaml
        """
        if thresholds_path is None:
            thresholds_path = Path(__file__).parent / 'thresholds.yaml'
        
        with open(thresholds_path, 'r') as f:
            self.thresholds = yaml.safe_load(f)
        
        # DCIR tracking: {soc_bin: [dcir_values]}
        self.dcir_history = {10: [], 50: [], 80: []}
        self.dcir_baseline = {10: None, 50: None, 80: None}
        
        # SOH tracking
        self.soh_history = []
        self.soh_timestamps = []
        
        # Stress tracking
        self.fast_charge_count = 0
        self.hours_at_high_temp = 0.0
        self.hours_at_high_soc = 0.0
        self.last_tick_time = None
        
        # Drift tracking (CUSUM-like)
        self.residual_history = deque(maxlen=1000)
        self.residual_mean = 0.0
        self.residual_std = 0.1
        
        # Minute rollup buffers
        self.minute_ticks = []
        self.minute_start = None
        
        # Daily summary
        self.daily_start = None
        self.daily_ticks = []
        
        # Charging event tracking
        self.charge_events = []
        self.last_charge_state = None
        
        # EV-specific metrics
        self.charging_energy_supplied = 0.0  # Wh supplied during charging
        self.charging_energy_stored = 0.0  # Wh actually stored
        self.driving_energy_consumed = 0.0  # Wh consumed during driving
        self.driving_distance_km = 0.0  # km driven
        self.current_charge_session_start = None
        self.current_charge_session_energy = 0.0
        self.nominal_range_km = 400.0  # Default EV range (configurable)
        
        # C-rate distribution for driving style
        self.c_rate_distribution = deque(maxlen=1000)
        self.thermal_stress_index = 0.0  # Weighted hours above 45°C
    
    def score_tick(self, ekf_out_dict: Dict):
        """
        Process a single tick from EKF.
        
        Args:
            ekf_out_dict: Output from BatteryEKF.step()
        """
        soc = ekf_out_dict['soc']
        residual = ekf_out_dict['residual']
        params = ekf_out_dict.get('params', {})
        v_pred = ekf_out_dict.get('v_pred', 0.0)
        temp_C = ekf_out_dict.get('temp_C', 25.0)
        
        # Update residual tracking
        self.residual_history.append(residual * 1000)  # Convert to mV
        if len(self.residual_history) > 100:
            self.residual_mean = np.mean(self.residual_history)
            self.residual_std = np.std(self.residual_history) if len(self.residual_history) > 1 else 0.1
        
        # Track DCIR at nominal SOC bins
        soc_pct = int(soc * 100)
        for bin_soc in [10, 50, 80]:
            if abs(soc_pct - bin_soc) < 5:  # Within 5% of bin
                R0 = params.get('R0', 0.03)
                # Simple DCIR estimate (could be improved with pulse detection)
                # Relaxed residual threshold to 50mV for more data points
                if abs(residual) < 0.05:  # Near steady state (relaxed from 10mV to 50mV)
                    dcir = R0 * 1000  # mOhm
                    self.dcir_history[bin_soc].append(dcir)
                    # Establish baseline after 10 points
                    if self.dcir_baseline[bin_soc] is None and len(self.dcir_history[bin_soc]) >= 10:
                        self.dcir_baseline[bin_soc] = np.median(self.dcir_history[bin_soc][:min(50, len(self.dcir_history[bin_soc]))])
        
        # Track SOH (from capacity parameter)
        Q_Ah = params.get('Q_Ah', 2.0)
        soh_pct = (Q_Ah / 2.0) * 100  # Assuming 2.0 Ah is nominal
        self.soh_history.append(soh_pct)
        self.soh_timestamps.append(datetime.now())
        
        # Track charging events and efficiency
        I_A = ekf_out_dict.get('I_A', 0.0)
        V_V = ekf_out_dict.get('V_V', ekf_out_dict.get('v_pred', 3.7))
        dt_s = ekf_out_dict.get('dt_s', 1.0)
        is_charging = I_A > 0.1  # Current > 100mA indicates charging
        
        if is_charging:
            if self.last_charge_state is None or not self.last_charge_state:
                # Charge event started
                self.charge_events.append(datetime.now())
                self.current_charge_session_start = datetime.now()
                self.current_charge_session_energy = 0.0
            
            # Track energy supplied (power * time)
            power_supplied = abs(I_A * V_V)  # Watts
            energy_supplied = power_supplied * dt_s / 3600  # Wh
            self.charging_energy_supplied += energy_supplied
            self.current_charge_session_energy += energy_supplied
            
            # Estimate energy stored (accounting for losses)
            # Efficiency typically 85-95% for Li-ion
            eta_charge = params.get('eta', 0.98)  # Coulombic efficiency
            energy_stored = energy_supplied * eta_charge
            self.charging_energy_stored += energy_stored
        else:
            # Not charging - could be driving or idle
            if I_A < -0.1:  # Discharging (driving)
                # Track driving energy consumption
                power_consumed = abs(I_A * V_V)  # Watts
                energy_consumed = power_consumed * dt_s / 3600  # Wh
                self.driving_energy_consumed += energy_consumed
                
                # Estimate distance (simplified: assume constant efficiency)
                # Typical EV: 150-200 Wh/km
                efficiency_wh_per_km = 175.0  # Average
                distance_km = energy_consumed / efficiency_wh_per_km
                self.driving_distance_km += distance_km
                
                # Track C-rate for driving style
                if Q_Ah > 0:
                    c_rate = abs(I_A) / Q_Ah
                    self.c_rate_distribution.append(c_rate)
        
        self.last_charge_state = is_charging
        
        # Track fast charge
        # Estimate C-rate from current (assuming Q_Ah from params)
        if Q_Ah > 0:
            c_rate = abs(ekf_out_dict.get('I_A', 0.0)) / Q_Ah
            if c_rate > self.thresholds['fast_charge']['c_rate_warn']:
                self.fast_charge_count += 1
        
        # Track thermal stress
        if temp_C > self.thresholds['temp_stress']['high_temp_C']:
            if self.last_tick_time:
                dt = (datetime.now() - self.last_tick_time).total_seconds() / 3600
                self.hours_at_high_temp += dt
        
        # Track thermal stress index (weighted hours above 45°C)
        if temp_C > 45.0:
            if self.last_tick_time:
                dt = (datetime.now() - self.last_tick_time).total_seconds() / 3600
                # Weight increases with temperature
                weight = (temp_C - 45.0) / 20.0  # Linear weight from 45-65°C
                self.thermal_stress_index += dt * weight
        
        if soc > self.thresholds['temp_stress']['high_soc_threshold']:
            if self.last_tick_time:
                dt = (datetime.now() - self.last_tick_time).total_seconds() / 3600
                self.hours_at_high_soc += dt
        
        self.last_tick_time = datetime.now()
        
        # Add to minute buffer
        self.minute_ticks.append({
            'soc': soc,
            'residual': residual,
            'temp_C': temp_C,
            'params': params,
            'timestamp': datetime.now()
        })
        
        # Add to daily buffer
        self.daily_ticks.append({
            'soc': soc,
            'residual': residual,
            'temp_C': temp_C,
            'params': params,
            'timestamp': datetime.now()
        })
    
    def minute_rollup(self) -> Dict:
        """Compute minute-level summary."""
        if len(self.minute_ticks) == 0:
            return {
                'soc_mean': 0.5,
                'soc_std': 0.0,
                'residual_mean_mv': 0.0,
                'residual_std_mv': 0.0,
                'temp_mean_C': 25.0,
                'tick_count': 0
            }
        
        socs = [t['soc'] for t in self.minute_ticks]
        residuals = [t['residual'] * 1000 for t in self.minute_ticks]  # mV
        temps = [t['temp_C'] for t in self.minute_ticks]
        
        result = {
            'soc_mean': float(np.mean(socs)),
            'soc_std': float(np.std(socs)),
            'residual_mean_mv': float(np.mean(residuals)),
            'residual_std_mv': float(np.std(residuals)),
            'temp_mean_C': float(np.mean(temps)),
            'tick_count': len(self.minute_ticks)
        }
        
        # Clear minute buffer
        self.minute_ticks = []
        self.minute_start = None
        
        return result
    
    def daily_summary(self) -> Dict:
        """Compute daily summary."""
        if len(self.daily_ticks) == 0:
            return {
                'soh_pct': 100.0,
                'dsoh_pct_per_week': 0.0,
                'dcir_changes': {},
                'stress': {
                    'fast_charge_count': 0,
                    'hours_at_high_temp': 0.0,
                    'hours_at_high_soc': 0.0
                },
                'drift': {
                    'residual_mean_mv': 0.0,
                    'residual_std_mv': 0.0
                }
            }
        
        # SOH trend
        soh_pct = 100.0
        dsoh_pct_per_week = 0.0
        if len(self.soh_history) > 1:
            soh_pct = self.soh_history[-1]
            if len(self.soh_timestamps) > 1:
                dt = (self.soh_timestamps[-1] - self.soh_timestamps[0]).total_seconds() / (7 * 24 * 3600)
                if dt > 0:
                    dsoh = self.soh_history[-1] - self.soh_history[0]
                    dsoh_pct_per_week = dsoh / dt
        
        # DCIR changes
        dcir_changes = {}
        for bin_soc in [10, 50, 80]:
            if self.dcir_baseline[bin_soc] is not None and len(self.dcir_history[bin_soc]) > 0:
                current = np.median(self.dcir_history[bin_soc][-50:])
                rel_change = ((current - self.dcir_baseline[bin_soc]) / self.dcir_baseline[bin_soc]) * 100
                dcir_changes[f'soc_{bin_soc}'] = {
                    'current_mohm': float(current),
                    'baseline_mohm': float(self.dcir_baseline[bin_soc]),
                    'rel_change_pct': float(rel_change)
                }
        
        # Stress metrics
        stress = {
            'fast_charge_count': self.fast_charge_count,
            'hours_at_high_temp': self.hours_at_high_temp,
            'hours_at_high_soc': self.hours_at_high_soc
        }
        
        # Drift
        if len(self.residual_history) > 0:
            drift = {
                'residual_mean_mv': float(np.mean(self.residual_history)),
                'residual_std_mv': float(np.std(self.residual_history))
            }
        else:
            drift = {'residual_mean_mv': 0.0, 'residual_std_mv': 0.0}
        
        # Calculate charging count (last 7 days)
        charge_count = 0
        if len(self.charge_events) > 0:
            week_ago = datetime.now() - timedelta(days=7)
            charge_count = sum(1 for event in self.charge_events if event >= week_ago)
        
        # Predict RUL (Remaining Useful Life)
        rul_days, rul_confidence = self._predict_rul()
        
        # Calculate charging efficiency
        charging_efficiency = 0.0
        if self.charging_energy_supplied > 0:
            charging_efficiency = (self.charging_energy_stored / self.charging_energy_supplied) * 100
        
        # Calculate driving energy consumption (Wh/km)
        energy_consumption_wh_per_km = 0.0
        if self.driving_distance_km > 0:
            energy_consumption_wh_per_km = self.driving_energy_consumed / self.driving_distance_km
        
        # Calculate predicted range drop
        current_soh = soh_pct / 100.0
        range_drop_km = self.nominal_range_km * (1.0 - current_soh)
        predicted_range_km = self.nominal_range_km * current_soh
        
        # Calculate warranty health score (0-100)
        warranty_score = self._calculate_warranty_score(soh_pct, dsoh_pct_per_week, 
                                                         self.thermal_stress_index,
                                                         self.fast_charge_count)
        
        # Calculate driving style impact
        driving_style = self._analyze_driving_style()
        
        # SOH projection (6-month forecast)
        soh_projection = self._project_soh_6months(soh_pct, dsoh_pct_per_week)
        
        # Additional prediction metrics
        predictions = {
            'rul_days': rul_days,
            'rul_confidence': rul_confidence,
            'estimated_cycles_remaining': self._estimate_cycles_remaining(),
            'degradation_rate_per_month': abs(dsoh_pct_per_week * 4.33),  # Convert weekly to monthly
            'charging_efficiency_pct': charging_efficiency,
            'energy_consumption_wh_per_km': energy_consumption_wh_per_km,
            'predicted_range_km': predicted_range_km,
            'range_drop_km': range_drop_km,
            'warranty_health_score': warranty_score,
            'driving_style': driving_style,
            'thermal_stress_index': self.thermal_stress_index,
            'soh_projection_6months': soh_projection
        }
        
        result = {
            'soh_pct': soh_pct,
            'dsoh_pct_per_week': dsoh_pct_per_week,
            'dcir_changes': dcir_changes,
            'stress': stress,
            'drift': drift,
            'charge_count_week': charge_count,
            'predictions': predictions,
            'avg_temp_C': np.mean([t.get('temp_C', 25.0) for t in self.daily_ticks]) if self.daily_ticks else 25.0
        }
        
        return result
    
    def _predict_rul(self) -> tuple:
        """
        Predict Remaining Useful Life (RUL) in days.
        Returns: (rul_days, confidence) where confidence is 0-1
        """
        if len(self.soh_history) < 2:
            return (None, 0.0)
        
        # Get recent SOH trend
        recent_soh = self.soh_history[-min(100, len(self.soh_history)):]
        recent_times = self.soh_timestamps[-min(100, len(self.soh_timestamps)):]
        
        if len(recent_soh) < 2:
            return (None, 0.0)
        
        # Calculate degradation rate
        time_delta = (recent_times[-1] - recent_times[0]).total_seconds() / (24 * 3600)  # days
        soh_delta = recent_soh[-1] - recent_soh[0]
        
        if time_delta <= 0 or soh_delta >= 0:
            # No degradation or improving (unlikely), use conservative estimate
            degradation_rate = 0.1  # 0.1% per day
        else:
            degradation_rate = abs(soh_delta) / time_delta  # % per day
        
        # Predict when SOH reaches 80% (typical end-of-life threshold)
        current_soh = recent_soh[-1]
        target_soh = 80.0
        soh_to_lose = current_soh - target_soh
        
        if degradation_rate <= 0:
            rul_days = None
            confidence = 0.0
        else:
            rul_days = soh_to_lose / degradation_rate
            
            # Confidence based on data quality
            confidence = min(1.0, len(recent_soh) / 50.0)  # More data = higher confidence
            if time_delta < 7:
                confidence *= 0.5  # Less than a week of data = lower confidence
        
        return (rul_days, confidence)
    
    def _estimate_cycles_remaining(self) -> Optional[float]:
        """Estimate remaining charge cycles."""
        if len(self.soh_history) < 2:
            return None
        
        # Typical battery: 500-1000 cycles to 80% SOH
        # Estimate based on current SOH
        current_soh = self.soh_history[-1]
        
        if current_soh <= 80:
            return 0
        
        # Linear approximation: assume 1000 cycles to go from 100% to 80%
        cycles_used = ((100 - current_soh) / 20) * 1000
        cycles_remaining = max(0, 1000 - cycles_used)
        
        return cycles_remaining
    
    def _calculate_warranty_score(self, soh_pct: float, dsoh_per_week: float, 
                                  thermal_stress: float, fast_charge_count: int) -> float:
        """
        Calculate warranty health score (0-100).
        Higher score = better warranty compliance.
        """
        score = 100.0
        
        # SOH penalty (lose points if below 90%)
        if soh_pct < 90:
            score -= (90 - soh_pct) * 0.5  # -0.5 points per % below 90
        
        # Degradation rate penalty
        if abs(dsoh_per_week) > 0.5:  # Fast degradation
            score -= min(20, abs(dsoh_per_week) * 10)
        
        # Thermal stress penalty
        if thermal_stress > 10:  # More than 10 weighted hours above 45°C
            score -= min(15, (thermal_stress - 10) * 0.5)
        
        # Fast charge penalty (moderate)
        if fast_charge_count > 50:
            score -= min(10, (fast_charge_count - 50) * 0.1)
        
        return max(0.0, min(100.0, score))
    
    def _analyze_driving_style(self) -> Dict:
        """Analyze driving style based on C-rate distribution."""
        if len(self.c_rate_distribution) == 0:
            return {
                'style': 'unknown',
                'aggressiveness': 0.0,
                'avg_c_rate': 0.0,
                'max_c_rate': 0.0
            }
        
        c_rates = list(self.c_rate_distribution)
        avg_c_rate = np.mean(c_rates)
        max_c_rate = np.max(c_rates)
        
        # Classify driving style
        if avg_c_rate < 0.5:
            style = 'conservative'
            aggressiveness = 0.2
        elif avg_c_rate < 1.0:
            style = 'moderate'
            aggressiveness = 0.5
        elif avg_c_rate < 1.5:
            style = 'aggressive'
            aggressiveness = 0.7
        else:
            style = 'very_aggressive'
            aggressiveness = 0.9
        
        return {
            'style': style,
            'aggressiveness': aggressiveness,
            'avg_c_rate': float(avg_c_rate),
            'max_c_rate': float(max_c_rate)
        }
    
    def _project_soh_6months(self, current_soh: float, dsoh_per_week: float) -> List[Dict]:
        """Project SOH for next 6 months."""
        projection = []
        weeks = 26  # ~6 months
        
        for week in range(weeks + 1):
            projected_soh = current_soh + (dsoh_per_week * week)
            projection.append({
                'week': week,
                'soh_pct': max(0, min(100, projected_soh)),
                'date': (datetime.now() + timedelta(weeks=week)).isoformat()
            })
        
        return projection


# Global scorer instance (singleton pattern)
_scorer: Optional[BatteryScorer] = None


def get_scorer() -> BatteryScorer:
    """Get or create global scorer instance."""
    global _scorer
    if _scorer is None:
        _scorer = BatteryScorer()
    return _scorer


def score_tick(ekf_out_dict: Dict):
    """Convenience function to score a tick."""
    get_scorer().score_tick(ekf_out_dict)


def minute_rollup() -> Dict:
    """Convenience function for minute rollup."""
    return get_scorer().minute_rollup()


def daily_summary() -> Dict:
    """Convenience function for daily summary."""
    return get_scorer().daily_summary()

