"""Test Parquet API endpoints via HTTP requests."""
import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"


def test_endpoints():
    """Test all Parquet API endpoints via HTTP."""
    print("=" * 70)
    print("Testing Parquet API Endpoints (HTTP)")
    print("=" * 70)
    print(f"\nBase URL: {BASE_URL}")
    print("Note: Make sure the FastAPI server is running (uvicorn app.main:app)")
    print("=" * 70)
    
    # Test 1: List vehicles
    print("\n1. Testing GET /data/vehicles")
    print("-" * 70)
    try:
        response = requests.get(f"{BASE_URL}/data/vehicles", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found {data['count']} vehicle(s): {data['vehicles']}")
            vehicle_id = data['vehicles'][0] if data['vehicles'] else None
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Connection error: Is the server running?")
        print("   Start with: uvicorn app.main:app --reload")
        return
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    if not vehicle_id:
        print("⚠️  No vehicles found. Cannot test other endpoints.")
        return
    
    # Test 2: Get prediction metrics
    print(f"\n2. Testing GET /data/prediction-metrics?vehicle_id={vehicle_id}")
    print("-" * 70)
    try:
        response = requests.get(
            f"{BASE_URL}/data/prediction-metrics",
            params={"vehicle_id": vehicle_id},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            metrics = data['metrics']
            print(f"✅ Prediction metrics retrieved for vehicle {data['vehicle_id']}")
            print(f"   Current SOH: {metrics.get('current_soh_pct', 'N/A'):.1%}")
            print(f"   Degradation so far: {metrics.get('degradation_so_far_pct', 'N/A'):.2f}%")
            print(f"   Degradation rate: {metrics.get('degradation_rate_pct_per_month', 'N/A'):.3f}%/month")
            rul = metrics.get('rul_months')
            if rul:
                print(f"   RUL: {rul:.1f} months ({metrics.get('rul_years', 'N/A'):.1f} years)")
            else:
                print(f"   RUL: Not degrading")
            print(f"   Range loss: {metrics.get('range_loss_km', 'N/A'):.1f} km")
            print(f"   Thermal stress index: {metrics.get('thermal_stress_index', 'N/A'):.2f}")
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Get daily summaries
    print(f"\n3. Testing GET /data/daily-summaries?vehicle_id={vehicle_id}&limit=5")
    print("-" * 70)
    try:
        response = requests.get(
            f"{BASE_URL}/data/daily-summaries",
            params={"vehicle_id": vehicle_id, "limit": 5},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Retrieved {data['count']} daily summaries")
            if data['count'] > 0:
                first = data['summaries'][0]
                print(f"   First summary date: {first.get('date', 'N/A')}")
                print(f"   Energy in: {first.get('energy_in_kwh', first.get('energy_in_wh', 'N/A'))} kWh")
                print(f"   Energy out: {first.get('energy_out_kwh', first.get('energy_out_wh', 'N/A'))} kWh")
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 4: Get EKF timeseries
    print(f"\n4. Testing GET /data/ekf-timeseries?vehicle_id={vehicle_id}&limit=10")
    print("-" * 70)
    try:
        response = requests.get(
            f"{BASE_URL}/data/ekf-timeseries",
            params={"vehicle_id": vehicle_id, "limit": 10},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Retrieved {data['count']} EKF timeseries records")
            if data['count'] > 0:
                first = data['timeseries'][0]
                print(f"   First record time_s: {first.get('time_s', 'N/A')}")
                print(f"   SOC: {first.get('soc', 'N/A'):.3f}")
                print(f"   SOH: {first.get('soh', 'N/A'):.3f}")
                print(f"   Voltage prediction: {first.get('v_pred', 'N/A'):.2f} V")
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 70)
    print("✅ All endpoint tests completed!")
    print("=" * 70)
    print("\nTo test manually, visit: http://localhost:8000/docs")


if __name__ == "__main__":
    test_endpoints()

