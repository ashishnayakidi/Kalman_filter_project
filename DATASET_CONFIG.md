# Dataset Configuration

## Current Configuration: B0005 Only

The system is currently configured to use **only the B0005 dataset** from the NASA battery aging dataset.

### Files Used

- **Raw Data**: `data/raw/B0005.mat`
- **Processed CSV**: `data/processed/B0005_flat.csv`
- **EKF Timeseries**: `data/processed/B0005_flat_ekf_timeseries.csv`

### Where B0005 is Referenced

1. **`scripts/nasa_load.py`**:
   - Default battery: `B0005`
   - Battery key detection prioritizes `B0005` over other keys

2. **`scripts/run_replay.py`**:
   - Default CSV path: `data/processed/B0005_flat.csv`
   - Output: `data/processed/B0005_flat_ekf_timeseries.csv`

3. **`frontend/app.py`**:
   - Data loading: `data/processed/B0005_flat_ekf_timeseries.csv`
   - Referenced in 3 locations (fetch, load initial data, history endpoint)

### Adding Other Datasets Later

To support other batteries (B0006, B0007, etc.) in the future:

1. **Update `scripts/nasa_load.py`**:
   - Add other battery keys to the detection list
   - Process other `.mat` files

2. **Update `frontend/app.py`**:
   - Make the dataset path configurable via environment variable
   - Or add dataset selection UI

3. **Update `scripts/run_replay.py`**:
   - Already supports custom CSV paths via `--csv-path`

### Environment Variable (Future)

Consider adding:
```bash
BATTERY_DATASET=B0005  # Default to B0005
```

Then update code to use:
```python
BATTERY_DATASET = os.getenv('BATTERY_DATASET', 'B0005')
ekf_csv = Path(...) / f'data/processed/{BATTERY_DATASET}_flat_ekf_timeseries.csv'
```

