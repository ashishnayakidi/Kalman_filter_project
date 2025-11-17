// Fleet Leads
let allCandidates = [];

async function loadLeads() {
    try {
        const response = await fetch('/api/fleet/leads');
        const data = await response.json();
        
        if (data.error) {
            console.error('Error:', data.error);
            return;
        }
        
        allCandidates = data.candidates || [];
        filterAndDisplayLeads();
        
    } catch (error) {
        console.error('Error loading leads:', error);
    }
}

function filterAndDisplayLeads() {
    const filter = document.getElementById('priority-filter').value;
    let candidates = allCandidates;
    
    if (filter !== 'all') {
        candidates = candidates.filter(c => c.priority === filter);
    }
    
    // Update summary
    document.getElementById('total-candidates').textContent = allCandidates.length;
    const highPriority = allCandidates.filter(c => c.priority === 'high').length;
    document.getElementById('high-priority').textContent = highPriority;
    const avgSoh = allCandidates.length > 0 ?
        allCandidates.reduce((sum, c) => sum + c.soh, 0) / allCandidates.length : 0;
    document.getElementById('avg-soh').textContent = avgSoh.toFixed(1) + '%';
    
    // Display table
    if (candidates.length > 0) {
        let html = '<table class="table table-striped"><thead><tr><th>VIN</th><th>Model</th><th>Region</th><th>SOH</th><th>RUL (days)</th><th>Warranty Score</th><th>Priority</th><th>Reasons</th></tr></thead><tbody>';
        candidates.forEach(c => {
            html += `<tr>
                <td>${c.vin}</td>
                <td>${c.model}</td>
                <td>${c.region}</td>
                <td>${c.soh.toFixed(1)}%</td>
                <td>${c.rul_days ? c.rul_days.toFixed(0) : 'N/A'}</td>
                <td>${c.warranty_score ? c.warranty_score.toFixed(0) : 'N/A'}</td>
                <td><span class="badge bg-${c.priority === 'high' ? 'danger' : 'warning'}">${c.priority}</span></td>
                <td>${c.reasons.join(', ')}</td>
            </tr>`;
        });
        html += '</tbody></table>';
        document.getElementById('leads-table').innerHTML = html;
    } else {
        document.getElementById('leads-table').innerHTML = '<p class="text-muted">No lead generation candidates at this time</p>';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    loadLeads();
    document.getElementById('priority-filter').addEventListener('change', filterAndDisplayLeads);
    setInterval(loadLeads, 60000);
});


