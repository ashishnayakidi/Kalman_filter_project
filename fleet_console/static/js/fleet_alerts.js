// Fleet Alerts
async function loadAlerts() {
    try {
        // Load vehicles at risk
        const riskResponse = await fetch('/api/fleet/vehicles_at_risk?limit=50');
        const riskData = await riskResponse.json();
        
        if (riskData.vehicles && riskData.vehicles.length > 0) {
            let html = '<table class="table table-striped"><thead><tr><th>VIN</th><th>Model</th><th>Region</th><th>SOH</th><th>Degradation Rate</th><th>RUL (days)</th><th>Risk Score</th></tr></thead><tbody>';
            riskData.vehicles.forEach(v => {
                html += `<tr>
                    <td>${v.vin}</td>
                    <td>${v.model}</td>
                    <td>${v.region}</td>
                    <td>${v.soh.toFixed(1)}%</td>
                    <td>${(v.degradation_rate || 0).toFixed(2)}%/month</td>
                    <td>${v.rul_days ? v.rul_days.toFixed(0) : 'N/A'}</td>
                    <td>${v.risk_score.toFixed(1)}</td>
                </tr>`;
            });
            html += '</tbody></table>';
            document.getElementById('vehicles-at-risk').innerHTML = html;
        } else {
            document.getElementById('vehicles-at-risk').innerHTML = '<p class="text-muted">No vehicles at risk</p>';
        }
        
        // Load alerts
        const alertsResponse = await fetch('/api/fleet/alerts');
        const alertsData = await alertsResponse.json();
        
        const alerts = alertsData.alerts || [];
        const critical = alerts.filter(a => a.severity === 'critical').length;
        const high = alerts.filter(a => a.severity === 'high').length;
        const medium = alerts.filter(a => a.severity === 'medium').length;
        const low = alerts.filter(a => a.severity === 'low').length;
        
        document.getElementById('critical-count').textContent = critical;
        document.getElementById('high-count').textContent = high;
        document.getElementById('medium-count').textContent = medium;
        document.getElementById('low-count').textContent = low;
        
        // Display recent alerts
        if (alerts.length > 0) {
            let html = '';
            alerts.slice(0, 20).forEach(alert => {
                const severityIcon = {
                    'critical': '🔴',
                    'high': '🟠',
                    'medium': '🟡',
                    'low': '🟢'
                }[alert.severity] || '⚪';
                
                html += `<div class="alert alert-${alert.severity === 'critical' ? 'danger' : alert.severity === 'high' ? 'warning' : 'info'}">
                    <strong>${severityIcon} ${alert.alert_type.toUpperCase()}</strong> - VIN: <code>${alert.vin}</code><br>
                    ${alert.message}<br>
                    <small>${new Date(alert.created_at).toLocaleString()}</small>
                </div>`;
            });
            document.getElementById('alerts-list').innerHTML = html;
        } else {
            document.getElementById('alerts-list').innerHTML = '<p class="text-muted">No active alerts</p>';
        }
        
    } catch (error) {
        console.error('Error loading alerts:', error);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    loadAlerts();
    setInterval(loadAlerts, 30000);
});


