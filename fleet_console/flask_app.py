"""Fleet Monitoring Console - Flask Application."""
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fleet_console.database.models import (
    get_all_vehicles, get_all_latest_states, get_alerts,
    get_latest_battery_state, get_battery_states
)
from fleet_console.utils.fleet_analytics import (
    get_fleet_health_overview, get_regional_stats,
    get_vehicles_at_risk, get_historical_trends,
    get_usage_clusters, predict_failures, get_lead_generation_candidates
)

app = Flask(__name__, 
            template_folder=Path(__file__).parent / 'templates',
            static_folder=Path(__file__).parent / 'static')
CORS(app)
app.secret_key = 'fleet-console-secret-key-change-in-production'
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True


@app.route('/')
def index():
    """Fleet console home page."""
    return render_template('fleet_index.html')


@app.route('/map')
def map_view():
    """Vehicle map view."""
    return render_template('fleet_map.html')


@app.route('/overview')
def overview():
    """Fleet health overview."""
    return render_template('fleet_overview.html')


@app.route('/alerts')
def alerts():
    """Alerts and ranking."""
    return render_template('fleet_alerts.html')


@app.route('/analytics')
def analytics():
    """Analytics and trends."""
    return render_template('fleet_analytics.html')


@app.route('/leads')
def leads():
    """Lead generation."""
    return render_template('fleet_leads.html')


# API Endpoints

@app.route('/api/fleet/vehicles')
def api_vehicles():
    """Get all vehicles."""
    try:
        vehicles = get_all_vehicles()
        return jsonify({
            'vehicles': [v.to_dict() for v in vehicles]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fleet/map_data')
def api_map_data():
    """Get map data with vehicle locations and SOH."""
    try:
        vehicles = get_all_vehicles()
        latest_states = get_all_latest_states()
        
        map_data = []
        for vehicle in vehicles:
            state = latest_states.get(vehicle.vin)
            if not state or not vehicle.latitude or not vehicle.longitude:
                continue
            
            # Color by SOH
            if state.soh >= 90:
                color = "green"
                status = "Excellent"
            elif state.soh >= 80:
                color = "yellow"
                status = "Good"
            else:
                color = "red"
                status = "Poor"
            
            map_data.append({
                'vin': vehicle.vin,
                'model': vehicle.model,
                'region': vehicle.region,
                'soh': state.soh,
                'soc': state.soc,
                'status': status,
                'color': color,
                'lat': vehicle.latitude,
                'lon': vehicle.longitude
            })
        
        return jsonify({'map_data': map_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fleet/overview')
def api_overview():
    """Get fleet health overview."""
    try:
        overview = get_fleet_health_overview()
        regional_stats = get_regional_stats()
        return jsonify({
            'overview': overview,
            'regional_stats': regional_stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fleet/vehicles_at_risk')
def api_vehicles_at_risk():
    """Get vehicles at risk."""
    try:
        limit = request.args.get('limit', 50, type=int)
        at_risk = get_vehicles_at_risk(limit=limit)
        return jsonify({'vehicles': at_risk})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fleet/alerts')
def api_alerts():
    """Get alerts."""
    try:
        vin = request.args.get('vin')
        severity = request.args.get('severity')
        alerts = get_alerts(vin=vin, severity=severity, resolved=False)
        return jsonify({
            'alerts': [a.to_dict() for a in alerts]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fleet/trends')
def api_trends():
    """Get historical trends."""
    try:
        vin = request.args.get('vin')
        days = request.args.get('days', 90, type=int)
        trends = get_historical_trends(vin=vin, days=days)
        return jsonify(trends)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fleet/clusters')
def api_clusters():
    """Get usage clusters."""
    try:
        clusters = get_usage_clusters()
        return jsonify(clusters)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fleet/predictions')
def api_predictions():
    """Get failure predictions."""
    try:
        predictions = predict_failures()
        return jsonify({'predictions': predictions})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fleet/leads')
def api_leads():
    """Get lead generation candidates."""
    try:
        candidates = get_lead_generation_candidates()
        return jsonify({'candidates': candidates})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)

