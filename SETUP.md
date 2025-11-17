# Setup Guide

Complete setup instructions for the Battery Health Monitor system.

## Prerequisites

- **Python 3.11+** (3.13 recommended)
- **macOS** (M1/M2 recommended for Metal acceleration) or **Linux**
- **Ollama** (optional, for AI features) - [Download](https://ollama.ai)
- **~2GB free space** for model file (if using local GGUF)
- **Git** (for cloning repository)

## Step 1: Clone Repository

```bash
git clone https://github.com/ashishnayakidi/Kalman_filter_project.git
cd Kalman_filter_project
```

## Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

## Step 3: Install Dependencies

```bash
# Install all required packages
pip install -r requirements.txt

# Or use Makefile
make install
```

**Key Dependencies:**
- FastAPI, Flask (web frameworks)
- NumPy, SciPy, Pandas (data processing)
- DuckDB, PyArrow (Parquet/analytics)
- llama-cpp-python (AI model)
- Plotly (charts)

## Step 4: Setup AI Model (Optional but Recommended)

### Option A: Using Ollama (Recommended)

1. **Install Ollama**:
   - Visit: https://ollama.ai/download
   - Download and install for your OS

2. **Start Ollama**:
   ```bash
   ollama serve
   ```

3. **Pull the Model**:
   ```bash
   ollama pull sam860/lfm2:350m
   ```

4. **Verify Installation**:
   ```bash
   ollama list
   # Should show: sam860/lfm2:350m
   ```

### Option B: Using Local GGUF File

1. **Download Model**:
   - Download `LFM2-350M-Q4_K_M.gguf` from HuggingFace
   - Place it in `models/` directory

2. **Create Directory** (if needed):
   ```bash
   mkdir -p models
   ```

3. **Verify File**:
   ```bash
   ls -lh models/LFM2-350M-Q4_K_M.gguf
   ```

The system will automatically use the local file if Ollama is unavailable.

## Step 5: Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Create .env file
touch .env
```

Add the following configuration:

```env
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

# AI Model Configuration
OLLAMA_MODEL=sam860/lfm2:350m
OLLAMA_BASE_URL=http://localhost:11434
MODEL_PATH=models/LFM2-350M-Q4_K_M.gguf

# Email Configuration (Optional, for sending reports)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=battery-monitor@yourdomain.com
```

**Note**: For Gmail, you need to use an [App Password](https://support.google.com/accounts/answer/185833), not your regular password.

## Step 6: Prepare Data (Optional)

If you have battery data to process:

### For NASA Dataset:
```bash
# Download and process NASA B0005 dataset
python scripts/nasa_load.py --battery B0005
```

### For Custom Data:
1. Place `.mat` files in `data/raw/` or `~/Downloads/`
2. The system will automatically detect and process them

## Step 7: Start the Application

### Start FastAPI Backend

```bash
# From project root
make run
# Or directly:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend will be available at: http://localhost:8000

### Start Flask Frontend

```bash
# From project root
make run-frontend
# Or directly:
cd frontend && python flask_app.py
```

Frontend will be available at: http://localhost:5001

**Note**: The Flask frontend includes the FastAPI backend, so you can run just the Flask app if preferred.

## Step 8: Verify Installation

1. **Check Backend**:
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status":"ok","version":"0.1.0"}
   ```

2. **Check Frontend**:
   - Open browser: http://localhost:5001
   - Should see the dashboard

3. **Check AI Model**:
   - Go to Chat page
   - Type "hello" - should get a friendly response
   - Type "what is my battery health?" - should get AI analysis

## Troubleshooting

### Python Import Errors

```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Add project root to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Ollama Not Working

1. **Check if Ollama is running**:
   ```bash
   curl http://localhost:11434/api/tags
   ```

2. **Start Ollama**:
   ```bash
   ollama serve
   ```

3. **Verify model is installed**:
   ```bash
   ollama list
   ```

4. **Install model if missing**:
   ```bash
   ollama pull sam860/lfm2:350m
   ```

### Port Already in Use

If port 5001 or 8000 is already in use:

```bash
# Find process using port
lsof -ti:5001
lsof -ti:8000

# Kill process (replace PID)
kill -9 <PID>
```

Or change ports in:
- Flask: `frontend/flask_app.py` (line 496)
- FastAPI: `uvicorn` command (change `--port`)

### Missing Dependencies

```bash
# Reinstall dependencies
pip install -r requirements.txt --upgrade
```

### Data Not Loading

1. **Check data directory**:
   ```bash
   ls -la data/parquet/
   ls -la data/ekf_output/
   ```

2. **Verify Parquet files exist**:
   ```bash
   python -c "import duckdb; conn = duckdb.connect(); print(conn.execute('SELECT COUNT(*) FROM read_parquet(\"data/parquet/timeseries/**/*.parquet\")').fetchone())"
   ```

### Email Not Sending

1. **Check SMTP configuration** in `.env`
2. **For Gmail**: Use App Password, not regular password
3. **Test SMTP connection**:
   ```bash
   python -c "import smtplib; server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls(); print('Connected')"
   ```

## Development Setup

### Running Tests

```bash
# Run all tests
make test
# Or
pytest tests/
```

### Code Formatting

```bash
# Install development tools
pip install black flake8

# Format code
black .
```

### Debug Mode

Flask runs in debug mode by default. For production, set:
```python
app.run(host='0.0.0.0', port=5001, debug=False)
```

## Production Deployment

### Environment Variables

Ensure all sensitive data is in `.env` file (not committed to git).

### Process Management

Use a process manager like `systemd`, `supervisor`, or `PM2`:

**Example systemd service** (`/etc/systemd/system/battery-monitor.service`):
```ini
[Unit]
Description=Battery Health Monitor
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/Kalman_filter_project
Environment="PATH=/path/to/.venv/bin"
ExecStart=/path/to/.venv/bin/python frontend/flask_app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Next Steps

1. **Process Your Data**: Run the data pipeline scripts if you have battery data
2. **Explore Dashboard**: Navigate to http://localhost:5001
3. **Try AI Chat**: Ask questions about battery health
4. **Generate Reports**: Create weekly health reports
5. **Configure Alerts**: Adjust thresholds in `agent/thresholds.yaml`

## Getting Help

- **Issues**: Open an issue on GitHub
- **Documentation**: See [README.md](README.md) for project overview
- **Configuration**: See `DATASET_CONFIG.md` for dataset configuration

## Quick Reference

```bash
# Start services
make run-frontend          # Start Flask (includes FastAPI)
make run                   # Start FastAPI only

# Data processing
python scripts/batch_ekf_processing.py
python scripts/daily_summaries.py
python scripts/prediction_metrics.py

# Testing
make test                  # Run tests
pytest tests/              # Run specific tests

# Cleanup
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -name "*.pyc" -delete
```

