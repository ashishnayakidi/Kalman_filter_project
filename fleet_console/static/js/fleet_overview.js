// Fleet Overview
async function loadOverview() {
    try {
        const response = await fetch('/api/fleet/overview');
        const data = await response.json();
        
        if (data.error) {
            console.error('Error:', data.error);
            return;
        }
        
        const overview = data.overview || {};
        const regional = data.regional_stats || {};
        
        // Update metrics
        document.getElementById('total-vehicles').textContent = overview.total_vehicles || 0;
        document.getElementById('avg-soh').textContent = (overview.avg_soh || 0).toFixed(1) + '%';
        document.getElementById('avg-degradation').textContent = (overview.avg_degradation_rate || 0).toFixed(2) + '%/month';
        document.getElementById('at-risk').textContent = overview.vehicles_at_risk || 0;
        
        // SOH Distribution Chart
        const dist = overview.soh_distribution || {};
        const distTrace = {
            x: ['Excellent (≥90%)', 'Good (80-90%)', 'Fair (70-80%)', 'Poor (<70%)'],
            y: [dist.excellent || 0, dist.good || 0, dist.fair || 0, dist.poor || 0],
            type: 'bar',
            marker: { color: ['green', 'yellow', 'orange', 'red'] }
        };
        
        Plotly.newPlot('soh-distribution-chart', [distTrace], {
            title: 'Battery Health Distribution',
            yaxis: { title: 'Number of Vehicles' }
        });
        
        // Regional Stats Table
        let html = '<table class="table table-striped"><thead><tr><th>Region</th><th>Vehicles</th><th>Avg SOH</th></tr></thead><tbody>';
        for (const [region, stats] of Object.entries(regional)) {
            html += `<tr><td>${region}</td><td>${stats.vehicles || 0}</td><td>${(stats.avg_soh || 0).toFixed(1)}%</td></tr>`;
        }
        html += '</tbody></table>';
        document.getElementById('regional-stats').innerHTML = html || '<p class="text-muted">No regional data available</p>';
        
    } catch (error) {
        console.error('Error loading overview:', error);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    loadOverview();
    setInterval(loadOverview, 30000);
});


