"""Generate sample fleet data for testing."""
import requests
import json
from datetime import datetime, timedelta
import random

API_URL = "http://localhost:8000/fleet/ingest"

# Sample vehicles
VEHICLES = [
    {"vin": "VIN001", "model": "Model X", "region": "California", "lat": 37.7749, "lon": -122.4194},
    {"vin": "VIN002", "model": "Model Y", "region": "California", "lat": 34.0522, "lon": -118.2437},
    {"vin": "VIN003", "model": "Model X", "region": "Texas", "lat": 29.7604, "lon": -95.3698},
    {"vin": "VIN004", "model": "Model Z", "region": "New York", "lat": 40.7128, "lon": -74.0060},
    {"vin": "VIN005", "model": "Model Y", "region": "Florida", "lat": 25.7617, "lon": -80.1918},
]

def generate_sample_data(vin: str, model: str, region: str, lat: float, lon: float, days_back: int = 7):
    """Generate sample telematics data for a vehicle."""
    base_time = datetime.now() - timedelta(days=days_back)
    
    # Vary SOH based on vehicle (for demo)
    base_soh = random.uniform(75, 100)
    if "VIN001" in vin:
        base_soh = 95  # Excellent
    elif "VIN002" in vin:
        base_soh = 85  # Good
    elif "VIN003" in vin:
        base_soh = 75  # Poor
    
    data_points = []
    for i in range(days_back * 24):  # Hourly data
        timestamp = base_time + timedelta(hours=i)
        
        # Simulate battery behavior
        soc = random.uniform(0.2, 1.0)
        voltage = 3.0 + soc * 1.2  # 3.0V to 4.2V
        current = random.uniform(-2.0, 2.0)  # Discharge/charge
        temperature = random.uniform(20, 35)
        if region == "Texas":
            temperature = random.uniform(30, 50)  # Hotter in Texas
        
        data_points.append({
            "vin": vin,
            "timestamp": timestamp.isoformat() + "Z",
            "latitude": lat + random.uniform(-0.01, 0.01),
            "longitude": lon + random.uniform(-0.01, 0.01),
            "voltage": round(voltage, 2),
            "current": round(current, 2),
            "temperature": round(temperature, 1),
            "model": model,
            "region": region
        })
    
    return data_points

def main():
    """Generate and send sample fleet data."""
    print("Generating sample fleet data...")
    
    all_data = []
    for vehicle in VEHICLES:
        print(f"Generating data for {vehicle['vin']}...")
        data = generate_sample_data(
            vehicle['vin'],
            vehicle['model'],
            vehicle['region'],
            vehicle['lat'],
            vehicle['lon']
        )
        all_data.extend(data)
    
    print(f"\nGenerated {len(all_data)} data points")
    print("Sending to API...")
    
    # Send in batches
    batch_size = 100
    for i in range(0, len(all_data), batch_size):
        batch = all_data[i:i+batch_size]
        try:
            response = requests.post(
                f"{API_URL}/batch",
                json={"data": batch},
                timeout=30
            )
            if response.status_code == 200:
                print(f"  Sent batch {i//batch_size + 1} ({len(batch)} points)")
            else:
                print(f"  Error in batch {i//batch_size + 1}: {response.status_code}")
        except Exception as e:
            print(f"  Error sending batch: {e}")
    
    print("\n✅ Sample fleet data generated!")
    print("\nNext steps:")
    print("1. Start Streamlit: streamlit run fleet_console/app.py")
    print("2. View the dashboard at http://localhost:8501")

if __name__ == "__main__":
    main()


