// Dashboard functionality
let updateInterval;

async function updateDashboard() {
    try {
        // Get state
        const stateRes = await fetch('/api/state');
        const state = await stateRes.json();
        
        // Calculate SOH
        const Q_current = state.params?.Q_Ah || 2.0;
        const Q_nominal = 2.0;
        const soh = (Q_current / Q_nominal) * 100;
        const soc = (state.soc || 0) * 100;

        // Update metrics
        document.getElementById('soc-value').textContent = soc.toFixed(1) + '%';
        document.getElementById('soc-progress').style.width = soc + '%';
        document.getElementById('soh-value').textContent = soh.toFixed(1) + '%';
        document.getElementById('soh-progress').style.width = soh + '%';
        
        // Get history for voltage
        const historyRes = await fetch('/api/history');
        const history = await historyRes.json();
        
        if (history.length > 0) {
            const last = history[history.length - 1];
            const voltage = last.v_pred || last.V_V || 3.7;
            document.getElementById('voltage-value').textContent = voltage.toFixed(3) + ' V';
        }

        // Get daily for temperature and predictions
        const dailyRes = await fetch('/api/daily');
        const daily = await dailyRes.json();
        const temp = daily.avg_temp_C || 25.0;
        document.getElementById('temp-value').textContent = temp.toFixed(1) + '°C';
        
        // Update RUL
        const predictions = daily.predictions || {};
        const rulDays = predictions.rul_days;
        const rulConfidence = predictions.rul_confidence || 0;
        if (rulDays !== null && rulDays !== undefined) {
            let rulText;
            if (rulDays > 365) {
                rulText = `${(rulDays/365).toFixed(1)}y`;
            } else if (rulDays > 30) {
                rulText = `${(rulDays/30).toFixed(0)}mo`;
            } else {
                rulText = `${rulDays.toFixed(0)}d`;
            }
            document.getElementById('rul-value').textContent = rulText;
            document.getElementById('rul-confidence').textContent = `(${(rulConfidence*100).toFixed(0)}% confidence)`;
        } else {
            document.getElementById('rul-value').textContent = 'N/A';
            document.getElementById('rul-confidence').textContent = '(insufficient data)';
        }
        
        // Update charge count
        const chargeCount = daily.charge_count_week || 0;
        document.getElementById('charge-count').textContent = chargeCount;

        // Update charts
        updateCharts(history);
    } catch (error) {
        console.error('Error updating dashboard:', error);
    }
}

function updateCharts(history) {
    if (history.length === 0) return;

    // SOC/SOH chart
    const socSohData = history.map((h, i) => ({
        x: i,
        soc: (h.soc || 0) * 100,
        soh: ((h.params?.Q_Ah || 2.0) / 2.0) * 100
    }));

    const socSohTrace1 = {
        x: socSohData.map(d => d.x),
        y: socSohData.map(d => d.soc),
        name: 'SOC',
        type: 'scatter',
        mode: 'lines'
    };

    const socSohTrace2 = {
        x: socSohData.map(d => d.x),
        y: socSohData.map(d => d.soh),
        name: 'SOH',
        type: 'scatter',
        mode: 'lines',
        yaxis: 'y2'
    };

    Plotly.newPlot('soc-soh-chart', [socSohTrace1, socSohTrace2], {
        xaxis: { title: 'Time Index' },
        yaxis: { title: 'SOC (%)' },
        yaxis2: { title: 'SOH (%)', overlaying: 'y', side: 'right' }
    });

    // Voltage chart
    const voltageData = history.map((h, i) => ({
        x: i,
        voltage: h.v_pred || h.V_V || 3.7,
        residual: (h.residual || 0) * 1000
    }));

    const voltageTrace1 = {
        x: voltageData.map(d => d.x),
        y: voltageData.map(d => d.voltage),
        name: 'Voltage',
        type: 'scatter',
        mode: 'lines'
    };

    const voltageTrace2 = {
        x: voltageData.map(d => d.x),
        y: voltageData.map(d => d.residual),
        name: 'Residual (mV)',
        type: 'scatter',
        mode: 'lines',
        yaxis: 'y2'
    };

    Plotly.newPlot('voltage-chart', [voltageTrace1, voltageTrace2], {
        xaxis: { title: 'Time Index' },
        yaxis: { title: 'Voltage (V)' },
        yaxis2: { title: 'Residual (mV)', overlaying: 'y', side: 'right' }
    });
}

async function updateFetchStatus() {
    try {
        const res = await fetch('/api/fetch_status');
        const status = await res.json();
        const statusEl = document.getElementById('fetch-status');
        if (status.last_fetch_time) {
            const lastFetch = new Date(status.last_fetch_time);
            statusEl.textContent = `Last fetched: ${lastFetch.toLocaleString()}`;
        } else {
            statusEl.textContent = 'No data fetched yet';
        }
    } catch (error) {
        console.error('Error fetching status:', error);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    updateDashboard();
    updateFetchStatus();
    
    // Update every 5 seconds
    updateInterval = setInterval(updateDashboard, 5000);
    
    // Fetch button
    document.getElementById('fetch-btn').addEventListener('click', async function() {
        const btn = this;
        btn.disabled = true;
        btn.textContent = 'Fetching...';
        
        try {
            const res = await fetch('/api/fetch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ force: true })
            });
            const data = await res.json();
            
            if (data.error) {
                alert('Error: ' + data.error);
            } else if (data.success) {
                alert('Fetch started! Processing in background. Check terminal for progress. This may take a few minutes.');
                // Update status after a short delay
                setTimeout(() => {
                    updateFetchStatus();
                }, 2000);
            } else {
                alert('Fetch response: ' + (data.message || 'Unknown response'));
            }
        } catch (error) {
            alert('Error: ' + error.message);
        } finally {
            // Re-enable button after a delay
            setTimeout(() => {
                btn.disabled = false;
                btn.textContent = '🔄 Fetch Latest Data';
            }, 1000);
        }
    });
});
