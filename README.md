# Battery Health Monitor

A production-ready battery state estimation and health monitoring system that uses Extended Kalman Filter (EKF) for real-time state estimation and AI-powered analytics for health insights.

## Overview

This system processes battery telemetry data to provide:
- **Real-time State Estimation**: SOC (State of Charge) and SOH (State of Health) using 1-RC Thevenin Extended Kalman Filter
- **Health Analytics**: Degradation tracking, RUL prediction, thermal stress monitoring
- **AI-Powered Insights**: Natural language Q&A and weekly health reports using LFM2-350M
- **Interactive Dashboard**: Real-time metrics, charts, and visualizations
- **Data Pipeline**: Scalable processing from raw data to analytics-ready Parquet format

## Architecture

```
┌─────────────────┐
│  Raw Data       │ → Pickle/CSV files → 80M+ rows
│  (Telemetry)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Data Pipeline  │ → Parquet Conversion → EKF Processing
│  (6 Phases)     │ → Daily Summaries → Prediction Metrics
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Storage Layer  │ → Partitioned Parquet + DuckDB
│  (Parquet)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Backend API    │ → FastAPI: /data/* endpoints
│  (FastAPI)      │ → /report/* (AI endpoints)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Frontend       │ → Flask: Dashboard, Chat, Reports
│  (Flask)        │
└─────────────────┘
```

## Key Features

### Core Engine
- **1-RC Thevenin EKF**: Real-time SOC/SOH estimation with voltage prediction
- **DCIR Tracking**: Dynamic internal resistance at 10%, 50%, 80% SOC
- **Stress Monitoring**: Thermal stress, fast charge events, high SOC duration
- **Drift Detection**: Residual analysis for model accuracy
- **RUL Prediction**: Remaining Useful Life with confidence intervals

### Frontend Dashboard
- **Real-time Metrics**: SOC, SOH, voltage, temperature, charging efficiency
- **Health Score**: 0-100 composite score with breakdown
- **Interactive Charts**: SOC/SOH trends, voltage predictions, temperature history
- **Time Range Filtering**: 24h, 7d, 30d, 3m, All
- **Alert System**: Automatic detection of critical issues
- **Trend Indicators**: Visual indicators for improving/degrading metrics

### AI Features
- **Intent-Aware Chat**: Natural conversation with battery health Q&A
- **Weekly Reports**: AI-generated reports in layman-friendly language
- **Email Reports**: Send reports via email (SMTP configured)

### Data Processing
- **Scalable Pipeline**: Handles 80M+ rows efficiently
- **Partitioned Storage**: Parquet files organized by vehicle_id and date
- **Batch Processing**: Vehicle-by-vehicle EKF processing
- **Daily Aggregation**: Energy, efficiency, temperature statistics
- **Prediction Metrics**: Degradation rates, RUL, range loss, thermal stress

## Tech Stack

### Backend
- **FastAPI**: REST API for data queries and AI endpoints
- **Flask**: Frontend web server
- **DuckDB**: In-process SQL analytics on Parquet files
- **PyArrow**: Parquet I/O and data processing

### Core Processing
- **NumPy/SciPy**: EKF mathematics and numerical operations
- **Pandas**: Data manipulation and analysis
- **Scikit-learn**: Machine learning utilities

### Frontend
- **HTML/CSS/JavaScript**: Dashboard UI
- **Bootstrap 5**: Responsive styling
- **Plotly**: Interactive charts and visualizations

### AI
- **LFM2-350M**: Local First Model via Ollama (with GGUF fallback)
- **llama-cpp-python**: Local model inference

## Project Structure

```
Kalman_filter_project/
├── agent/                    # Core battery agent
│   ├── ekf.py               # Extended Kalman Filter implementation
│   ├── ocv.py               # Open Circuit Voltage lookup
│   ├── scoring.py           # Health scoring (DCIR, stress, RUL)
│   └── thresholds.yaml      # Health thresholds
├── app/                     # FastAPI backend
│   ├── main.py             # FastAPI application
│   ├── routes/              # API endpoints
│   │   ├── parquet.py      # Data query endpoints
│   │   ├── report.py       # AI report endpoints
│   │   └── ...
│   └── core/               # Configuration and models
├── frontend/                 # Flask frontend
│   ├── flask_app.py        # Flask application
│   ├── templates/          # HTML templates
│   ├── static/             # CSS, JavaScript
│   └── utils/              # Shared utilities
├── lfm/                     # AI model integration
│   ├── runner.py           # Model runner (Ollama/local)
│   └── prompts.py          # Prompt templates
├── scripts/                 # Data processing scripts
│   ├── batch_ekf_processing.py
│   ├── daily_summaries.py
│   ├── prediction_metrics.py
│   └── ...
├── data/                    # Data storage
│   ├── parquet/            # Processed Parquet files
│   ├── ekf_output/         # EKF timeseries
│   ├── daily_summaries/    # Daily aggregations
│   └── prediction_metrics/ # Prediction metrics
└── requirements.txt
```

## Data Pipeline

The system processes data through 6 phases:

1. **Phase 0**: Dataset freeze and versioning
2. **Phase 1**: CSV → Parquet conversion (partitioned)
3. **Phase 2**: Data quality checks (optional)
4. **Phase 3**: Batch EKF processing
5. **Phase 4**: Daily summaries generation
6. **Phase 5**: Prediction metrics calculation
7. **Phase 6**: Backend API endpoints

## API Endpoints

### Data Endpoints (`/data/*`)
- `GET /data/prediction-metrics` - Get prediction metrics for a vehicle
- `GET /data/daily-summaries` - Get daily summaries with date filtering
- `GET /data/ekf-timeseries` - Get detailed EKF timeseries data
- `GET /data/vehicles` - List all available vehicles

### AI Endpoints (`/report/*`)
- `POST /report/qna` - Q&A about battery health
- `POST /report/weekly` - Generate weekly report

### Frontend Endpoints (`/api/*`)
- `GET /api/state` - Current EKF state
- `GET /api/history` - EKF history for charts
- `POST /api/ask` - Chat Q&A
- `POST /api/weekly_report` - Weekly report
- `POST /api/send_report_email` - Email report

## Performance

- **EKF Processing**: ~1000 ticks/second
- **Storage**: 2.45GB Parquet (from 10GB CSV)
- **Query Speed**: Sub-second queries on partitioned Parquet
- **AI Inference**: 10-30 tokens/second (Ollama)

## License

MIT

Our dataset originates from the EVBattery Dataset by Zheng et al., distributed under the Creative Commons BY-NC-SA 4.0 License.
We use this data solely for non-commercial research and hackathon demonstration purposes.
Full attribution is provided to the original authors, and no redistribution or commercial use of the dataset is involved.

## Acknowledgments

- LFM2-350M (Local First Model)
- Ollama for model serving



For detailed setup instructions, see [SETUP.md](SETUP.md).
