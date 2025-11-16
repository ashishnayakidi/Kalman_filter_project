"""Extended Kalman Filter for battery state estimation (1-RC Thevenin model)."""
import numpy as np
from typing import Dict, Optional
from agent.ocv import ocv_lookup


class BatteryEKF:
    """
    1-RC Thevenin EKF for battery state estimation.
    
    States: [soc, v_rc]
    - soc: State of charge (0.0 to 1.0)
    - v_rc: RC branch voltage (V)
    """
    
    def __init__(self,
                 Q_Ah: float = 2.0,
                 R0: float = 0.03,
                 R1: float = 0.01,
                 C1: float = 2000.0,
                 eta: float = 0.98,
                 soc_init: float = 1.0,
                 Q_soc: float = 1e-7,
                 Q_vrc: float = 1e-5,
                 R_volt: float = 2.5e-5,
                 ocv_table: Optional = None):
        """
        Initialize EKF.
        
        Args:
            Q_Ah: Nominal capacity (Ah)
            R0: Series resistance (Ohm)
            R1: RC branch resistance (Ohm)
            C1: RC branch capacitance (F)
            eta: Coulombic efficiency
            soc_init: Initial SOC (0.0 to 1.0)
            Q_soc: Process noise covariance for SOC
            Q_vrc: Process noise covariance for v_rc
            R_volt: Measurement noise covariance for voltage
            ocv_table: OCV lookup table (DataFrame or None)
        """
        self.Q_Ah = Q_Ah
        self.R0 = R0
        self.R1 = R1
        self.C1 = C1
        self.eta = eta
        
        # State: [soc, v_rc]
        self.x = np.array([np.clip(soc_init, 0.0, 1.0), 0.0])
        
        # Covariance matrix
        self.P = np.diag([0.01, 0.001])  # Initial uncertainty
        
        # Process noise
        self.Q = np.diag([Q_soc, Q_vrc])
        
        # Measurement noise
        self.R = R_volt
        
        # OCV table
        self.ocv_table = ocv_table
        
        # History
        self.history = []
    
    def step(self, I_A: float, V_V: float, T_C: float, dt_s: float) -> Dict:
        """
        Perform one EKF step.
        
        Args:
            I_A: Current (A), positive for discharge
            V_V: Measured voltage (V)
            T_C: Temperature (C)
            dt_s: Time step (s)
        
        Returns:
            Dictionary with state, predictions, and diagnostics
        """
        soc, v_rc = self.x
        
        # Process model
        # SOC update: soc_next = soc - eta * I * dt / (Q_Ah * 3600)
        soc_next = soc - self.eta * I_A * dt_s / (self.Q_Ah * 3600)
        soc_next = np.clip(soc_next, 0.0, 1.0)
        
        # RC branch: vrc_next = exp(-dt/(R1*C1))*v_rc + R1*(1-exp(-dt/(R1*C1)))*I
        tau = self.R1 * self.C1
        alpha = np.exp(-dt_s / tau) if tau > 0 else 0.0
        v_rc_next = alpha * v_rc + self.R1 * (1 - alpha) * I_A
        
        # Predicted state
        x_pred = np.array([soc_next, v_rc_next])
        
        # State transition Jacobian
        F = np.array([
            [1.0, 0.0],
            [0.0, alpha]
        ])
        
        # Process noise Jacobian (identity for additive noise)
        G = np.eye(2)
        
        # Predict covariance
        P_pred = F @ self.P @ F.T + G @ self.Q @ G.T
        
        # Measurement model: V = OCV(soc, T) - v_rc - I*R0
        ocv = ocv_lookup(soc_next, T_C, self.ocv_table)
        V_pred = ocv - v_rc_next - I_A * self.R0
        
        # Measurement Jacobian
        # dV/dsoc = dOCV/dsoc (approximate as constant for small changes)
        dOCV_dSOC = 1.2  # Approximate from fallback OCV curve
        H = np.array([[dOCV_dSOC, -1.0]])
        
        # Innovation (residual)
        residual = V_V - V_pred
        
        # Innovation covariance
        S = H @ P_pred @ H.T + self.R
        
        # Kalman gain
        K = (P_pred @ H.T) / S
        
        # Update state
        self.x = x_pred + K.reshape(-1) * residual
        self.x[0] = np.clip(self.x[0], 0.0, 1.0)  # Clip SOC
        
        # Update covariance (Joseph form for numerical stability)
        I_KH = np.eye(2) - K @ H
        self.P = I_KH @ P_pred @ I_KH.T + self.R * (K @ K.T)
        
        # Store result
        result = {
            'soc': float(self.x[0]),
            'v_rc': float(self.x[1]),
            'v_pred': float(V_pred),
            'residual': float(residual),
            'cov': self.P.copy().tolist(),  # Convert to list for JSON serialization
            'params': {
                'Q_Ah': self.Q_Ah,
                'R0': self.R0,
                'R1': self.R1,
                'C1': self.C1,
                'eta': self.eta
            },
            'ocv': float(ocv),
            'temp_C': T_C
        }
        
        self.history.append(result)
        return result
    
    def reset(self, soc_init: float = 1.0):
        """Reset EKF to initial state."""
        self.x = np.array([np.clip(soc_init, 0.0, 1.0), 0.0])
        self.P = np.diag([0.01, 0.001])
        self.history = []
    
    def get_state(self) -> Dict:
        """Get current state."""
        return {
            'soc': float(self.x[0]),
            'v_rc': float(self.x[1]),
            'cov': self.P.tolist(),
            'params': {
                'Q_Ah': self.Q_Ah,
                'R0': self.R0,
                'R1': self.R1,
                'C1': self.C1,
                'eta': self.eta
            }
        }

