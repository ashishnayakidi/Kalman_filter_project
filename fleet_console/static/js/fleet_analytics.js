// Fleet Analytics
async function loadAnalytics() {
    try {
        // Load trends
        const trendsResponse = await fetch('/api/fleet/trends?days=90');
        const trendsData = await trendsResponse.json();
        
        if (trendsData.dates && trendsData.avg_soh) {
            const trace = {
                x: trendsData.dates,
                y: trendsData.avg_soh,
                type: 'scatter',
                mode: 'lines+markers',
                name: 'Fleet Average SOH'
            };
            
            Plotly.newPlot('trends-chart', [trace], {
                title: 'Fleet Average SOH Over Time',
                xaxis: { title: 'Date' },
                yaxis: { title: 'SOH (%)', range: [0, 100] }
            });
        } else {
            document.getElementById('trends-chart').innerHTML = '<p class="text-muted">Insufficient data for trend analysis</p>';
        }
        
        // Load clusters
        const clustersResponse = await fetch('/api/fleet/clusters');
        const clustersData = await clustersResponse.json();
        
        // Fast charge cluster
        const fastCharge = clustersData.high_fast_charge || [];
        if (fastCharge.length > 0) {
            let html = '<table class="table table-striped"><thead><tr><th>VIN</th><th>Model</th><th>Max Current</th></tr></thead><tbody>';
            fastCharge.forEach(v => {
                html += `<tr><td>${v.vin}</td><td>${v.model}</td><td>${v.max_current.toFixed(2)}A</td></tr>`;
            });
            html += '</tbody></table>';
            document.getElementById('fast-charge-cluster').innerHTML = html;
        } else {
            document.getElementById('fast-charge-cluster').innerHTML = '<p class="text-muted">No vehicles with high fast charge usage</p>';
        }
        
        // High temp cluster
        const highTemp = clustersData.high_temp || [];
        if (highTemp.length > 0) {
            let html = '<table class="table table-striped"><thead><tr><th>VIN</th><th>Model</th><th>Avg Temp</th></tr></thead><tbody>';
            highTemp.forEach(v => {
                html += `<tr><td>${v.vin}</td><td>${v.model}</td><td>${v.avg_temp.toFixed(1)}°C</td></tr>`;
            });
            html += '</tbody></table>';
            document.getElementById('high-temp-cluster').innerHTML = html;
        } else {
            document.getElementById('high-temp-cluster').innerHTML = '<p class="text-muted">No vehicles with high temperature exposure</p>';
        }
        
        // Load predictions
        const predictionsResponse = await fetch('/api/fleet/predictions');
        const predictionsData = await predictionsResponse.json();
        
        const predictions = predictionsData.predictions || [];
        if (predictions.length > 0) {
            let html = '<table class="table table-striped"><thead><tr><th>VIN</th><th>Model</th><th>Region</th><th>SOH</th><th>RUL (days)</th><th>Failure Probability</th><th>Est. Failure Date</th></tr></thead><tbody>';
            predictions.forEach(p => {
                html += `<tr>
                    <td>${p.vin}</td>
                    <td>${p.model}</td>
                    <td>${p.region}</td>
                    <td>${p.soh.toFixed(1)}%</td>
                    <td>${p.rul_days ? p.rul_days.toFixed(0) : 'N/A'}</td>
                    <td>${(p.failure_probability * 100).toFixed(1)}%</td>
                    <td>${p.estimated_failure_date ? new Date(p.estimated_failure_date).toLocaleDateString() : 'N/A'}</td>
                </tr>`;
            });
            html += '</tbody></table>';
            document.getElementById('predictions-table').innerHTML = html;
        } else {
            document.getElementById('predictions-table').innerHTML = '<p class="text-muted">No failure predictions at this time</p>';
        }
        
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    loadAnalytics();
    setInterval(loadAnalytics, 60000);
});


