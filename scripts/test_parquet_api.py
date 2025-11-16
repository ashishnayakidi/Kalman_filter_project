"""Test script for Parquet API endpoints."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.routes.parquet import (
    get_prediction_metrics,
    get_daily_summaries,
    get_ekf_timeseries,
    list_vehicles
)
import asyncio


async def test_endpoints():
    """Test all Parquet API endpoints."""
    print("=" * 70)
    print("Testing Parquet API Endpoints")
    print("=" * 70)
    
    # Test 1: List vehicles
    print("\n1. Testing /data/vehicles")
    print("-" * 70)
    try:
        vehicles_result = await list_vehicles()
        print(f"✅ Found {vehicles_result['count']} vehicle(s): {vehicles_result['vehicles']}")
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    if vehicles_result['count'] == 0:
        print("⚠️  No vehicles found. Cannot test other endpoints.")
        return
    
    vehicle_id = vehicles_result['vehicles'][0]
    
    # Test 2: Get prediction metrics
    print(f"\n2. Testing /data/prediction-metrics?vehicle_id={vehicle_id}")
    print("-" * 70)
    try:
        metrics_result = await get_prediction_metrics(vehicle_id=vehicle_id)
        metrics = metrics_result['metrics']
        print(f"✅ Prediction metrics retrieved for vehicle {vehicle_id}")
        print(f"   Current SOH: {metrics.get('current_soh_pct', 'N/A'):.1%}")
        print(f"   Degradation so far: {metrics.get('degradation_so_far_pct', 'N/A'):.2f}%")
        print(f"   Degradation rate: {metrics.get('degradation_rate_pct_per_month', 'N/A'):.3f}%/month")
        print(f"   RUL: {metrics.get('rul_months', 'N/A')} months" if metrics.get('rul_months') else "   RUL: Not degrading")
        print(f"   Range loss: {metrics.get('range_loss_km', 'N/A'):.1f} km")
        print(f"   Thermal stress index: {metrics.get('thermal_stress_index', 'N/A'):.2f}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Get daily summaries
    print(f"\n3. Testing /data/daily-summaries?vehicle_id={vehicle_id}&limit=5")
    print("-" * 70)
    try:
        summaries_result = await get_daily_summaries(vehicle_id=vehicle_id, limit=5)
        print(f"✅ Retrieved {summaries_result['count']} daily summaries")
        if summaries_result['count'] > 0:
            first = summaries_result['summaries'][0]
            print(f"   First summary date: {first.get('date', 'N/A')}")
            print(f"   Energy in: {first.get('energy_in_kwh', 'N/A'):.2f} kWh")
            print(f"   Energy out: {first.get('energy_out_kwh', 'N/A'):.2f} kWh")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 4: Get EKF timeseries
    print(f"\n4. Testing /data/ekf-timeseries?vehicle_id={vehicle_id}&limit=10")
    print("-" * 70)
    try:
        timeseries_result = await get_ekf_timeseries(vehicle_id=vehicle_id, limit=10)
        print(f"✅ Retrieved {timeseries_result['count']} EKF timeseries records")
        if timeseries_result['count'] > 0:
            first = timeseries_result['timeseries'][0]
            print(f"   First record time_s: {first.get('time_s', 'N/A')}")
            print(f"   SOC: {first.get('soc', 'N/A'):.3f}")
            print(f"   SOH: {first.get('soh', 'N/A'):.3f}")
            print(f"   Voltage prediction: {first.get('v_pred', 'N/A'):.2f} V")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 70)
    print("✅ All endpoint tests completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_endpoints())

