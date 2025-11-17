# Fleet Monitoring Console

Fleet monitoring dashboard for OEMs and fleet managers to monitor thousands of batteries, identify early degradation, and enable predictive maintenance.

## Features

- **Vehicle Map View**: Interactive map with color-coded SOH status
- **Fleet Health Overview**: Aggregate metrics and SOH distribution
- **Alerts & Ranking**: Vehicles at risk, sorted by priority
- **Analytics**: Historical trends, usage clusters, failure predictions
- **Lead Generation**: Identify vehicles due for pack replacement

## Quick Start

### 1. Start the Fleet Console

```bash
# From project root
make run-fleet
# Or directly:
cd fleet_console && python flask_app.py
```

The console will be available at: http://localhost:5002

### 2. Ingest Telematics Data

Use the FastAPI endpoint to ingest vehicle data:

```bash
# Single data point
curl -X POST http://localhost:8000/fleet/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "vin": "VIN123456",
    "timestamp": "2024-01-15T10:00:00Z",
    "latitude": 37.7749,
    "longitude": -122.4194,
    "voltage": 3.9,
    "current": 1.5,
    "temperature": 25.0,
    "model": "Model X",
    "region": "California"
  }'
```

### 3. View Dashboard

Open the Streamlit app and navigate through the tabs:
- **Map View**: See all vehicles on a map
- **Fleet Overview**: Aggregate health metrics
- **Alerts**: Vehicles requiring attention
- **Analytics**: Trends and patterns
- **Lead Generation**: Replacement candidates

## API Endpoints

### Ingest Telematics Data
- `POST /fleet/ingest` - Single data point
- `POST /fleet/ingest/batch` - Multiple data points

### Query Data
- `GET /fleet/vehicles` - List all vehicles
- `GET /fleet/vehicles/{vin}/state` - Get vehicle state
- `GET /fleet/alerts` - List alerts

## Data Model

### Vehicle
- VIN (unique identifier)
- Model
- Region
- Registration date
- Location (lat/lon)

### Battery State
- VIN
- Timestamp
- SOC, SOH
- Temperature, Voltage, Current
- Warranty score
- RUL (days)
- Degradation rate

### Alert
- VIN
- Alert type (degradation, thermal, fast_charge, warranty)
- Severity (low, medium, high, critical)
- Message
- Timestamp

## Production Considerations

For production use, replace the in-memory storage with:
- **PostgreSQL** for vehicle and alert data
- **InfluxDB** or **TimescaleDB** for time-series battery states
- **Redis** for real-time caching

## Integration

The fleet console uses the same EKF and scoring engine as the customer app, ensuring consistent battery health assessment across both products.

