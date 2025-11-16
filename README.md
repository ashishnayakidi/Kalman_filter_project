# Battery Agent - EKF + LFM2-350M

A production-ready battery state estimation system using Extended Kalman Filter (EKF) for real-time monitoring and LFM2-350M for AI-powered health reports.

## Features

- **1-RC Thevenin EKF** for battery state estimation (SOC, RC voltage)
- **DCIR tracking** at multiple SOC levels
- **Stress monitoring** (thermal, fast charge)
- **Drift detection** using residual analysis
- **NASA dataset support** with automatic flattening
- **FastAPI backend** with RESTful endpoints
- **Local LFM2-350M** for Q&A and weekly reports (GGUF via llama-cpp-python)

## Prerequisites

- Python 3.11+
- macOS (M1/M2 recommended for Metal acceleration)
- ~2GB free space for model file

## Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# Or use make
make install
```

### 2. Download LFM2-350M Model

Download the GGUF quantized model (Q4_K_M recommended):

```bash
# Create models directory
mkdir -p models

# Download from HuggingFace (example - adjust URL as needed)
# Visit: https://huggingface.co/models and search for "LFM2-350M"
# Or use:
# wget -O models/LFM2-350M-Q4_K_M.gguf <model_url>
```

**Note:** Place the downloaded `LFM2-350M-Q4_K_M.gguf` file in the `models/` directory.

### 3. Configure Environment

Copy `.env.example` to `.env` and adjust if needed:

```bash
cp .env.example .env
```

Default values should work for most cases.

### 4. Download and Process NASA Dataset

```bash
# Download and flatten NASA B0005 dataset
python scripts/nasa_load.py --battery B0005

# This will:
# - Attempt to download B0005.mat (or use existing file)
# - Flatten to data/processed/B0005_flat.csv
```

**Manual Download:** If automatic download fails, visit:
- https://data.nasa.gov/dataset/Lithium-Ion-Battery-Aging-Data/5K9Q-7V7H
- Download and extract the dataset
- Place `B0005.mat` in `data/raw/`
- Run the script again

### 5. Replay Data Through EKF

```bash
# Process CSV through EKF
python scripts/run_replay.py --csv-path data/processed/B0005_flat.csv

# Or use make
make replay
```

This generates:
- `data/processed/B0005_flat_ekf_timeseries.csv` - Full EKF output
- Daily summary printed to console

### 6. Start API Server

```bash
# Start FastAPI server
uvicorn app.main:app --reload

# Or use make
make run
```

Server will be available at: http://127.0.0.1:8000

- API Docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## API Endpoints

### Health & Info
- `GET /health` - Health check
- `GET /` - API info

### EKF Operations
- `POST /ekf/tick` - Process single tick
  ```json
  {
    "I_A": 1.2,
    "V_V": 3.9,
    "T_C": 25.0,
    "dt_s": 1.0
  }
  ```
- `GET /ekf/state` - Get current EKF state
- `POST /ekf/reset?soc_init=1.0` - Reset EKF

### Data Ingestion
- `POST /ingest/replay` - Replay CSV file
  ```json
  {
    "csv_path": "data/processed/B0005_flat.csv"
  }
  ```

### Summaries
- `GET /summary/minute` - Minute-level rollup
- `GET /summary/daily` - Daily summary

### Reports (LFM-powered)
- `POST /report/qna` - Q&A about battery health
  ```json
  {
    "question": "Why did my battery health drop?"
  }
  ```
- `POST /report/weekly` - Generate weekly markdown report

## Example Usage

### Process a Single Tick

```bash
curl -X POST http://localhost:8000/ekf/tick \
  -H "Content-Type: application/json" \
  -d '{
    "I_A": 1.5,
    "V_V": 4.0,
    "T_C": 25.0,
    "dt_s": 1.0
  }'
```

### Get Current State

```bash
curl http://localhost:8000/ekf/state
```

### Get Daily Summary

```bash
curl http://localhost:8000/summary/daily
```

### Generate Weekly Report

```bash
curl -X POST http://localhost:8000/report/weekly
```

### Replay CSV

```bash
curl -X POST http://localhost:8000/ingest/replay \
  -H "Content-Type: application/json" \
  -d '{"csv_path": "data/processed/B0005_flat.csv"}'
```

## Project Structure

```
Kalman_filter_project/
├── app/                    # FastAPI application
│   ├── main.py            # FastAPI app entry
│   ├── routes/            # API routes
│   │   ├── health.py
│   │   ├── ekf.py
│   │   ├── ingest.py
│   │   ├── summary.py
│   │   └── report.py
│   └── core/              # Core config and models
│       ├── config.py
│       └── models.py
├── agent/                 # Battery agent
│   ├── ekf.py            # EKF implementation
│   ├── ocv.py            # OCV lookup
│   ├── scoring.py        # Health scoring
│   ├── summaries.py      # Summary formatting
│   ├── stream.py          # CSV streaming
│   └── thresholds.yaml    # Health thresholds
├── lfm/                   # LFM2-350M integration
│   ├── runner.py         # Model runner
│   └── prompts.py        # Prompt templates
├── scripts/               # Utility scripts
│   ├── nasa_load.py      # NASA data loader
│   └── run_replay.py     # Replay script
├── data/
│   ├── raw/              # Raw .mat files
│   └── processed/        # Processed CSVs
├── models/                # LFM2-350M GGUF files
├── tests/                 # Unit tests
├── requirements.txt
├── pyproject.toml
├── Makefile
└── README.md
```

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

### Model Not Found

If you see "Model file not found", ensure:
1. LFM2-350M-Q4_K_M.gguf is in `models/` directory
2. `MODEL_PATH` in `.env` points to correct location

### NASA Dataset Download Fails

1. Download manually from: https://data.nasa.gov/dataset/Lithium-Ion-Battery-Aging-Data/5K9Q-7V7H
2. Extract and place `.mat` file in `data/raw/`
3. Run `python scripts/nasa_load.py --battery B0005`

### Import Errors

Ensure you're in the project root and virtual environment is activated:
```bash
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Slow LFM Generation

- Reduce `max_tokens` in prompts
- Use smaller context window (`n_ctx` in `lfm/runner.py`)
- Close other applications to free up memory

## Performance Notes

- **EKF**: Processes ~1000 ticks/second (Python)
- **LFM2-350M**: ~2-5 tokens/second on M1 Air (Q4_K_M, Metal)
- **Replay**: ~10-30 seconds for typical NASA dataset cycle

## License

MIT

## Acknowledgments

- NASA Battery Dataset: https://data.nasa.gov/dataset/Lithium-Ion-Battery-Aging-Data
- LFM2-350M: Local First Model
- llama-cpp-python: https://github.com/abetlen/llama-cpp-python

