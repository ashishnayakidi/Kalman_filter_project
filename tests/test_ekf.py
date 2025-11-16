"""Tests for EKF."""
import pytest
import numpy as np
from agent.ekf import BatteryEKF


def test_ekf_initialization():
    """Test EKF initialization."""
    ekf = BatteryEKF(Q_Ah=2.0, R0=0.03, R1=0.01, C1=2000.0)
    state = ekf.get_state()
    assert 0.0 <= state['soc'] <= 1.0
    assert 'v_rc' in state
    assert 'params' in state


def test_ekf_step():
    """Test EKF step."""
    ekf = BatteryEKF(Q_Ah=2.0, R0=0.03, R1=0.01, C1=2000.0)
    out = ekf.step(I_A=1.5, V_V=4.0, T_C=25.0, dt_s=1.0)
    
    assert 0.0 <= out['soc'] <= 1.0
    assert 'v_rc' in out
    assert 'v_pred' in out
    assert 'residual' in out
    assert 'cov' in out
    assert 'params' in out


def test_ekf_reset():
    """Test EKF reset."""
    ekf = BatteryEKF(Q_Ah=2.0, R0=0.03, R1=0.01, C1=2000.0)
    ekf.step(I_A=1.0, V_V=3.8, T_C=25.0, dt_s=1.0)
    ekf.reset(soc_init=0.5)
    state = ekf.get_state()
    assert abs(state['soc'] - 0.5) < 0.01

