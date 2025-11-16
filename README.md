# Battery Health Monitor - EKF + LFM2-350M

A production-ready battery state estimation and health monitoring system using Extended Kalman Filter (EKF) for real-time SOC/SOH estimation and LFM2-350M (via Ollama) for AI-powered health reports and Q&A.

## Features

- **1-RC Thevenin EKF** for battery state estimation (SOC, RC voltage, capacity)
- **DCIR tracking** at multiple SOC levels (10%, 50%, 80%)
- **Stress monitoring** (thermal, fast charge, high SOC)
- **Drift detection** using residual analysis
- **RUL Prediction** (Remaining Useful Life) with confidence levels
- **Charging event tracking** and analysis
- **NASA dataset support** with automatic flattening and processing
- **Flask frontend** with real-time dashboard, AI chat, and weekly reports
- **Ollama integration** for LFM2-350M model inference (with local GGUF fallback)
- **Automatic hourly data fetching** from Downloads folder
- **Manual data fetch** with .mat file processing pipeline

## Prerequisites

- Python 3.11+
- macOS (M1/M2 recommended for Metal acceleration) or Linux
- Ollama installed (optional, for AI features) - [Install Ollama](https://ollama.ai)
- ~2GB free space for model file (if using local GGUF)

## Quick Start

### 1. Setup Environment

```bash
# Clone the repository
git clone https://github.com/ashishnayakidi/Kalman_filter_project.git
cd Kalman_filter_project

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# Or use make
make install
```

### 2. Setup Ollama (Recommended)

```bash
# Install Ollama (if not already installed)
# Visit: https://ollama.ai/download

# Pull the LFM2-350M model
ollama pull sam860/lfm2:350m
```

**Alternative:** If you prefer local GGUF file:
1. Download `LFM2-350M-Q4_K_M.gguf` from HuggingFace
2. Place it in `models/` directory
3. The system will automatically use it if Ollama is unavailable

### 3. Configure Environment

Create a `.env` file (optional, defaults work for most cases):

```bash
# EKF Parameters
Q_AH_INIT=2.0
R0_INIT=0.03
R1_INIT=0.01
C1_INIT=2000.0
ETA_INIT=0.98
SOC_INIT=1.0

# EKF Noise Parameters
EKF_Q_SOC=1e-7
EKF_Q_VRC=1e-5
EKF_R_VOLT=2.5e-5

# Model Configuration
OLLAMA_MODEL=sam860/lfm2:350m
OLLAMA_BASE_URL=http://localhost:11434
MODEL_PATH=models/LFM2-350M-Q4_K_M.gguf
```

### 4. Download and Process NASA Dataset

```bash
# Download and flatten NASA B0005 dataset
python scripts/nasa_load.py --battery B0005

# This will:
# - Attempt to download B0005.mat (or use existing file)
# - Flatten to data/processed/B0005_flat.csv
```

**Manual Download:** If automatic download fails:
1. Visit: https://data.nasa.gov/dataset/Lithium-Ion-Battery-Aging-Data/5K9Q-7V7H
2. Download and extract the dataset
3. Place `B0005.mat` in `data/raw/` or `~/Downloads/`
4. Run the script again

### 5. Start the Application

```bash
# Start Flask frontend (includes FastAPI backend)
make run-frontend
# Or directly:
cd frontend && python flask_app.py
```

The application will be available at:
- **Frontend**: http://localhost:5001
- **API Docs**: http://localhost:5001/api/docs (if FastAPI routes are exposed)

### 6. Using the Application

1. **Dashboard**: View real-time metrics (SOC, SOH, RUL, Voltage, Temperature, Charging count)
2. **Chat**: Ask questions about battery health using AI
3. **Reports**: Generate weekly battery health reports in layman-friendly language
4. **Data Fetching**: 
   - Automatic: Runs every hour, checks Downloads folder for new .mat files
   - Manual: Click "Fetch Latest Data" button in dashboard

## Project Structure

```
Kalman_filter_project/
├── agent/                    # Battery agent core
│   ├── ekf.py               # EKF implementation
│   ├── ocv.py               # OCV lookup and derivation
│   ├── scoring.py           # Health scoring (DCIR, stress, drift, RUL)
│   ├── stream.py            # CSV streaming
│   ├── summaries.py        # Summary formatting
│   └── thresholds.yaml      # Health thresholds
├── app/                     # FastAPI backend
│   ├── main.py             # FastAPI app entry
│   ├── routes/              # API routes
│   │   ├── health.py
│   │   ├── ekf.py
│   │   ├── ingest.py
│   │   ├── summary.py
│   │   └── report.py
│   └── core/                # Core config and models
│       ├── config.py
│       └── models.py
├── frontend/                 # Flask frontend
│   ├── flask_app.py        # Flask application
│   ├── templates/          # HTML templates
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── dashboard.html
│   │   ├── chat.html
│   │   └── reports.html
│   ├── static/             # Static files
│   │   ├── css/
│   │   └── js/
│   └── utils/              # Shared utilities
│       └── core.py
├── lfm/                     # LFM2-350M integration
│   ├── runner.py           # Model runner (Ollama + local)
│   └── prompts.py          # Prompt templates
├── scripts/                 # Utility scripts
│   ├── nasa_load.py        # NASA data loader
│   ├── run_replay.py       # Replay script
│   └── generate_nasa_like_data.py
├── data/
│   ├── raw/                # Raw .mat files
│   └── processed/          # Processed CSVs
├── models/                  # LFM2-350M GGUF files (optional)
├── tests/                   # Unit tests
├── requirements.txt
├── pyproject.toml
├── Makefile
└── README.md
```

## Key Features Explained

### Automatic Data Fetching

The system automatically:
1. Checks `~/Downloads` and `data/raw/` for `B0005.mat` files every hour
2. Flattens .mat files to CSV
3. Processes through EKF
4. Updates dashboard with new data

### RUL Prediction

- **Remaining Useful Life (RUL)**: Predicts when battery will reach 80% SOH
- **Confidence Level**: Based on data quality and history length
- **Display**: Shows in days, months, or years on dashboard

### Weekly Reports

AI-generated reports include:
- Executive summary in simple terms
- Charging activity analysis
- Battery degradation summary
- Remaining useful life prediction
- Actionable recommendations

All written in layman-friendly language, avoiding technical jargon.

### Dashboard Metrics

- **SOC**: State of Charge (0-100%)
- **SOH**: State of Health (0-100%, 100% = brand new)
- **RUL**: Remaining Useful Life with confidence
- **Voltage**: Current battery voltage
- **Temperature**: Average temperature
- **Charges/Week**: Number of charging events this week

## API Endpoints

### Health & Info
- `GET /health` - Health check
- `GET /api/state` - Get current EKF state
- `GET /api/daily` - Get daily summary
- `GET /api/minute` - Get minute rollup
- `GET /api/history` - Get EKF history for charts

### Data Operations
- `POST /api/fetch` - Manually trigger data fetch
- `GET /api/fetch_status` - Get fetch status

### Reports (AI-powered)
- `POST /api/ask` - Q&A about battery health
  ```json
  {
    "question": "Suggest general charging habits"
  }
  ```
- `POST /api/weekly_report` - Generate weekly markdown report

## Configuration

### EKF Parameters

Edit `.env` to adjust:
- `Q_AH_INIT`: Nominal capacity (Ah)
- `R0_INIT`: Series resistance (Ohm)
- `R1_INIT`: RC branch resistance (Ohm)
- `C1_INIT`: RC branch capacitance (F)
- `ETA_INIT`: Coulombic efficiency
- `SOC_INIT`: Initial SOC (0.0-1.0)
- `EKF_Q_SOC`: Process noise for SOC
- `EKF_Q_VRC`: Process noise for RC voltage
- `EKF_R_VOLT`: Measurement noise for voltage

### Health Thresholds

Edit `agent/thresholds.yaml` to adjust:
- SOH warning thresholds
- DCIR increase limits
- Temperature stress thresholds
- Fast charge C-rate limits
- Residual drift thresholds

## Testing

```bash
# Run all tests
make test
# Or
pytest -q tests/
```

## Troubleshooting

### Ollama Not Working

1. Ensure Ollama is running: `ollama serve`
2. Check if model is installed: `ollama list`
3. Install model: `ollama pull sam860/lfm2:350m`
4. System will fallback to local GGUF file if Ollama unavailable

### Model Not Found

If you see "Model not found", ensure:
1. Ollama is running with model installed, OR
2. `LFM2-350M-Q4_K_M.gguf` is in `models/` directory
3. `MODEL_PATH` in `.env` points to correct location

### NASA Dataset Download Fails

1. Download manually from: https://data.nasa.gov/dataset/Lithium-Ion-Battery-Aging-Data/5K9Q-7V7H
2. Extract and place `B0005.mat` in `data/raw/` or `~/Downloads/`
3. System will automatically detect and process it

### Import Errors

Ensure you're in the project root and virtual environment is activated:
```bash
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Slow AI Responses

- Ensure Ollama is running locally
- Check Ollama logs for issues
- Reduce `max_tokens` in prompts if needed
- Use smaller context window if using local GGUF

## Performance Notes

- **EKF**: Processes ~1000 ticks/second (Python)
- **LFM2-350M (Ollama)**: ~10-30 tokens/second
- **LFM2-350M (Local GGUF)**: ~2-5 tokens/second on M1 Air (Q4_K_M, Metal)
- **Data Processing**: ~10-30 seconds for typical NASA dataset cycle
- **Automatic Fetch**: Runs every hour in background thread

## Makefile Commands

```bash
make install      # Install dependencies
make run          # Start FastAPI backend
make run-frontend # Start Flask frontend
make test         # Run tests
make replay       # Process CSV through EKF
```

## License

MIT

## Acknowledgments

- **NASA Battery Dataset**: https://data.nasa.gov/dataset/Lithium-Ion-Battery-Aging-Data
- **LFM2-350M**: Local First Model
- **Ollama**: https://ollama.ai
- **llama-cpp-python**: https://github.com/abetlen/llama-cpp-python

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Contact

For issues and questions, please open an issue on GitHub: https://github.com/ashishnayakidi/Kalman_filter_project/issues
