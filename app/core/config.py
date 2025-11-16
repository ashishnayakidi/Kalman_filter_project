"""Configuration management."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Model path
MODEL_PATH = os.getenv('MODEL_PATH', 'models/LFM2-350M-Q4_K_M.gguf')

# EKF parameters
EKF_Q_SOC = float(os.getenv('EKF_Q_SOC', '1e-7'))
EKF_Q_VRC = float(os.getenv('EKF_Q_VRC', '1e-5'))
EKF_R_VOLT = float(os.getenv('EKF_R_VOLT', '2.5e-5'))

# Battery parameters
Q_AH_INIT = float(os.getenv('Q_AH_INIT', '2.0'))
R0_INIT = float(os.getenv('R0_INIT', '0.03'))
R1_INIT = float(os.getenv('R1_INIT', '0.01'))
C1_INIT = float(os.getenv('C1_INIT', '2000.0'))
ETA_INIT = float(os.getenv('ETA_INIT', '0.98'))
SOC_INIT = float(os.getenv('SOC_INIT', '1.0'))

# Data paths
DATA_RAW_DIR = Path('data/raw')
DATA_PROCESSED_DIR = Path('data/processed')

# Version
VERSION = "0.1.0"

