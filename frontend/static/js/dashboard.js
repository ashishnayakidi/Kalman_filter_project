// Dashboard functionality
let updateInterval;
let currentTimeRange = 'all'; // Default time range

// Update data points indicator
function updateDataPointsIndicator(historyLength, dailySummariesCount) {
    const indicator = document.getElementById('data-points-indicator');
    if (indicator) {
        let text = '';
        if (historyLength > 0) {
            text = `${historyLength.toLocaleString()} data points`;
        }
        if (dailySummariesCount !== null && dailySummariesCount !== undefined) {
            text += ` • ${dailySummariesCount} days`;
        }
        indicator.textContent = text;
    }
}

// Calculate date range based on selected time range
// Note: Our data is historical (2020-2021), so we use relative filtering from the data's end date
function getDateRange(range, dataEndDate = null) {
    // If we have a data end date, use it; otherwise use today (for future data)
    const referenceDate = dataEndDate ? new Date(dataEndDate) : new Date();
    let startDate, endDate;
    
    switch(range) {
        case '24h':
            startDate = new Date(referenceDate.getTime() - 24 * 60 * 60 * 1000);
            endDate = referenceDate;
            break;
        case '7d':
            startDate = new Date(referenceDate.getTime() - 7 * 24 * 60 * 60 * 1000);
            endDate = referenceDate;
            break;
        case '30d':
            startDate = new Date(referenceDate.getTime() - 30 * 24 * 60 * 60 * 1000);
            endDate = referenceDate;
            break;
        case '3m':
            startDate = new Date(referenceDate.getTime() - 90 * 24 * 60 * 60 * 1000);
            endDate = referenceDate;
            break;
        case 'all':
        default:
            startDate = null;
            endDate = null;
            break;
    }
    
    return {
        start: startDate ? startDate.toISOString().split('T')[0] : null,
        end: endDate ? endDate.toISOString().split('T')[0] : null
    };
}

// Get data date range from prediction metrics
// Default to data end date from our dataset (2021-10-05)
let dataDateRange = '2021-10-05';

async function updateDashboard() {
    try {
        // Get prediction metrics from new FastAPI endpoint
        let predictionMetrics = null;
        try {
            const metricsRes = await fetch('/api/prediction-metrics');
            if (metricsRes.ok) {
                const metricsData = await metricsRes.json();
                predictionMetrics = metricsData.metrics || metricsData;
                
                // Extract data date range from metrics (if available, use it; otherwise keep default)
                if (predictionMetrics.last_updated) {
                    // Use last_updated as the end date for filtering
                    dataDateRange = predictionMetrics.last_updated;
                }
            }
        } catch (e) {
            console.warn('Could not fetch prediction metrics:', e);
        }
        
        // Get date range based on current selection (using data's date range if available)
        const dateRange = getDateRange(currentTimeRange, dataDateRange);
        console.log('Current time range:', currentTimeRange, 'Date range:', dateRange);
        
        // Get state (fallback for real-time data)
        const stateRes = await fetch('/api/state');
        const state = await stateRes.json();
        
        // Calculate SOH from prediction metrics or state
        let soh, soc;
        if (predictionMetrics && predictionMetrics.current_soh_pct !== undefined) {
            soh = predictionMetrics.current_soh_pct * 100;
            soc = (state.soc || 0) * 100;
        } else {
            const Q_current = state.params?.Q_Ah || 2.0;
            const Q_nominal = 2.0;
            soh = (Q_current / Q_nominal) * 100;
            soc = (state.soc || 0) * 100;
        }

        // Update metrics (with null checks)
        const socValueEl = document.getElementById('soc-value');
        const socProgressEl = document.getElementById('soc-progress');
        const sohValueEl = document.getElementById('soh-value');
        const sohProgressEl = document.getElementById('soh-progress');
        
        if (socValueEl) socValueEl.textContent = soc.toFixed(1) + '%';
        if (socProgressEl) socProgressEl.style.width = soc + '%';
        if (sohValueEl) sohValueEl.textContent = soh.toFixed(1) + '%';
        if (sohProgressEl) sohProgressEl.style.width = soh + '%';
        
        // Get history for voltage and charts
        // For now, use in-memory history and filter by taking last N points
        // (EKF timeseries API has issues, will fix separately)
        let history = [];
        try {
            const historyRes = await fetch('/api/history');
            history = await historyRes.json();
            console.log('In-memory history length:', history.length);
            
            // Filter history by taking last N points based on time range
            // Since we have 643 days of data, calculate points based on sampling
            if (currentTimeRange !== 'all' && history.length > 0) {
                // Estimate: if we have ~80M rows over 643 days, that's ~124k rows per day
                // For filtering, take percentage of total based on time range
                const totalDays = 643; // From metadata
                let daysToShow;
                switch(currentTimeRange) {
                    case '24h':
                        daysToShow = 1;
                        break;
                    case '7d':
                        daysToShow = 7;
                        break;
                    case '30d':
                        daysToShow = 30;
                        break;
                    case '3m':
                        daysToShow = 90;
                        break;
                    default:
                        daysToShow = totalDays;
                }
                
                // Calculate how many points to show (proportional to days)
                const ratio = daysToShow / totalDays;
                const maxPoints = Math.max(100, Math.min(history.length, Math.floor(history.length * ratio)));
                const originalLength = history.length;
                history = history.slice(-maxPoints);
                console.log(`Filtered history: ${originalLength} -> ${history.length} points (showing last ${daysToShow} days of ${totalDays} total)`);
            } else {
                console.log('Showing all history data');
            }
        } catch (e) {
            console.error('Could not fetch history:', e);
        }
        
        if (history.length > 0) {
            const last = history[history.length - 1];
            const voltage = last.v_pred || last.V_V || 3.7;
            const voltageEl = document.getElementById('voltage-value');
            if (voltageEl) voltageEl.textContent = voltage.toFixed(3) + ' V';
        }

        // Get daily summaries for temperature (with date filtering)
        let temp = 25.0;
        let dailySummariesData = null;
        try {
            let dailySummariesUrl = '/api/daily-summaries';
            // Adjust limit based on time range
            const limit = currentTimeRange === '24h' ? 1 : 
                         currentTimeRange === '7d' ? 7 :
                         currentTimeRange === '30d' ? 30 :
                         currentTimeRange === '3m' ? 90 : 100;
            dailySummariesUrl += `?limit=${limit}`;
            
            if (dateRange.start && dateRange.end) {
                dailySummariesUrl += `&start_date=${dateRange.start}&end_date=${dateRange.end}`;
            }
            console.log('Fetching daily summaries:', dailySummariesUrl);
            const dailySummariesRes = await fetch(dailySummariesUrl);
            if (dailySummariesRes.ok) {
                dailySummariesData = await dailySummariesRes.json();
                console.log('Daily summaries response:', dailySummariesData.count, 'records');
                if (dailySummariesData.summaries && dailySummariesData.summaries.length > 0) {
                    // Get most recent summary in range
                    const latest = dailySummariesData.summaries[dailySummariesData.summaries.length - 1];
                    temp = latest.avg_temp_c || 25.0;
                }
            } else {
                console.warn('Daily summaries API failed:', dailySummariesRes.status);
            }
        } catch (e) {
            console.warn('Could not fetch daily summaries:', e);
            // Fallback to old endpoint
            try {
                const dailyRes = await fetch('/api/daily');
                const daily = await dailyRes.json();
                temp = daily.avg_temp_C || 25.0;
            } catch (e2) {
                console.warn('Fallback daily endpoint also failed:', e2);
            }
        }
        const tempValueEl = document.getElementById('temp-value');
        if (tempValueEl) tempValueEl.textContent = temp.toFixed(1) + '°C';
        
            // Update RUL from prediction metrics (for prediction panel, not main RUL card)
        if (predictionMetrics) {
            const rulMonths = predictionMetrics.rul_months;
            const rulConfidence = predictionMetrics.rul_confidence || 0;
            
            // Update prediction panel RUL (if it exists)
            const predictionRulEl = document.getElementById('prediction-rul');
            if (predictionRulEl) {
                if (rulMonths !== null && rulMonths !== undefined) {
                    let rulText;
                    if (rulMonths > 12) {
                        rulText = `${(rulMonths/12).toFixed(1)} years`;
                    } else if (rulMonths >= 1) {
                        rulText = `${rulMonths.toFixed(0)} months`;
                    } else {
                        rulText = `${(rulMonths*30).toFixed(0)} days`;
                    }
                    predictionRulEl.textContent = rulText;
                } else {
                    predictionRulEl.textContent = 'Not degrading';
                }
            }
            
            // Range remaining
            const currentRange = predictionMetrics.current_range_km || 0;
            const rangeLoss = predictionMetrics.range_loss_km || 0;
            const rangeValueEl = document.getElementById('range-value');
            const rangeDropEl = document.getElementById('range-drop');
            if (rangeValueEl) rangeValueEl.textContent = currentRange.toFixed(0) + ' km';
            if (rangeDropEl) {
                if (rangeLoss > 0) {
                    rangeDropEl.textContent = '- ' + rangeLoss.toFixed(0) + ' km from new';
                } else {
                    rangeDropEl.textContent = '';
                }
            }
            
            // Health status based on degradation
            const degradationSoFar = predictionMetrics.degradation_so_far_pct || 0;
            let healthStatus = '🟢 Excellent';
            let healthColor = 'border-success';
            if (degradationSoFar > 20) {
                healthStatus = '🔴 Poor';
                healthColor = 'border-danger';
            } else if (degradationSoFar > 10) {
                healthStatus = '🟡 Fair';
                healthColor = 'border-warning';
            }
            const healthStatusEl = document.getElementById('health-status');
            const healthStatusCardEl = document.getElementById('health-status-card');
            const warrantyScoreEl = document.getElementById('warranty-score');
            if (healthStatusEl) healthStatusEl.textContent = healthStatus;
            if (healthStatusCardEl) healthStatusCardEl.className = `card text-center ${healthColor}`;
            if (warrantyScoreEl) warrantyScoreEl.textContent = `Degradation: ${degradationSoFar.toFixed(2)}%`;
            
            // Charging efficiency
            const chargeEffTrend = predictionMetrics.charge_efficiency_trend || 0;
            const chargeEffEl = document.getElementById('charge-efficiency');
            if (chargeEffEl) chargeEffEl.textContent = (chargeEffTrend * 100).toFixed(1) + '%';
            
            // Update prediction panel with new metrics (already handled above)
            
            const degRate = predictionMetrics.degradation_rate_pct_per_month || 0;
            const predDegEl = document.getElementById('prediction-degradation');
            if (predDegEl) predDegEl.textContent = `${degRate.toFixed(3)}% per month`;
            
            const thermalStress = predictionMetrics.thermal_stress_index || 0;
            const predThermalEl = document.getElementById('prediction-thermal');
            if (predThermalEl) predThermalEl.textContent = `${thermalStress.toFixed(1)} weighted hours`;
            
            const habitScore = predictionMetrics.recharge_habit_score || 0;
            const predDrivingEl = document.getElementById('prediction-driving-style');
            if (predDrivingEl) predDrivingEl.textContent = `Habit Score: ${habitScore.toFixed(3)}`;
        } else {
            // Fallback to old daily endpoint
            const dailyRes = await fetch('/api/daily');
            const daily = await dailyRes.json();
            const predictions = daily.predictions || {};
            
            const rulDays = predictions.rul_days;
            const predictionRulEl = document.getElementById('prediction-rul');
            if (predictionRulEl) {
                if (rulDays !== null && rulDays !== undefined) {
                    let rulText;
                    if (rulDays > 365) {
                        rulText = `${(rulDays/365).toFixed(1)} years`;
                    } else if (rulDays > 30) {
                        rulText = `${(rulDays/30).toFixed(0)} months`;
                    } else {
                        rulText = `${rulDays.toFixed(0)} days`;
                    }
                    predictionRulEl.textContent = rulText;
                } else {
                    predictionRulEl.textContent = 'Insufficient data';
                }
            }
            
            const predictedRange = predictions.predicted_range_km || 0;
            const rangeDrop = predictions.range_drop_km || 0;
            const rangeValueEl2 = document.getElementById('range-value');
            const rangeDropEl2 = document.getElementById('range-drop');
            if (rangeValueEl2) rangeValueEl2.textContent = predictedRange.toFixed(0) + ' km';
            if (rangeDropEl2 && rangeDrop > 0) {
                rangeDropEl2.textContent = '- ' + rangeDrop.toFixed(0) + ' km from new';
            }
            
            const warrantyScore = predictions.warranty_health_score || 100;
            let healthStatus = '🟢 Excellent';
            let healthColor = 'border-success';
            if (warrantyScore < 70) {
                healthStatus = '🔴 Poor';
                healthColor = 'border-danger';
            } else if (warrantyScore < 85) {
                healthStatus = '🟡 Fair';
                healthColor = 'border-warning';
            }
            const healthStatusEl2 = document.getElementById('health-status');
            const healthStatusCardEl2 = document.getElementById('health-status-card');
            const warrantyScoreEl2 = document.getElementById('warranty-score');
            if (healthStatusEl2) healthStatusEl2.textContent = healthStatus;
            if (healthStatusCardEl2) healthStatusCardEl2.className = `card text-center ${healthColor}`;
            if (warrantyScoreEl2) warrantyScoreEl2.textContent = `Warranty Score: ${warrantyScore.toFixed(0)}/100`;
            
            const chargeEff = predictions.charging_efficiency_pct || 0;
            const chargeEffEl2 = document.getElementById('charge-efficiency');
            if (chargeEffEl2) chargeEffEl2.textContent = chargeEff > 0 ? chargeEff.toFixed(1) + '%' : 'N/A';
            
            const energyCons = predictions.energy_consumption_wh_per_km || 0;
            const energyConsEl = document.getElementById('energy-consumption');
            if (energyConsEl) energyConsEl.textContent = energyCons > 0 ? energyCons.toFixed(0) : 'N/A';
        }
        
        // Update charge count (fallback)
        try {
            const dailyRes = await fetch('/api/daily');
            const daily = await dailyRes.json();
            const chargeCount = daily.charge_count_week || 0;
            const chargeCountEl = document.getElementById('charge-count');
            if (chargeCountEl) chargeCountEl.textContent = chargeCount;
        } catch (e) {
            const chargeCountEl = document.getElementById('charge-count');
            if (chargeCountEl) chargeCountEl.textContent = '-';
        }
        
        // Energy consumption (fallback)
        if (!predictionMetrics) {
            try {
                const dailyRes = await fetch('/api/daily');
                const daily = await dailyRes.json();
                const energyCons = daily.predictions?.energy_consumption_wh_per_km || 0;
                const energyConsEl2 = document.getElementById('energy-consumption');
                if (energyConsEl2) energyConsEl2.textContent = energyCons > 0 ? energyCons.toFixed(0) : 'N/A';
            } catch (e) {
                const energyConsEl3 = document.getElementById('energy-consumption');
                if (energyConsEl3) energyConsEl3.textContent = 'N/A';
            }
        }

        // Update new features (with error handling to not break existing functionality)
        try {
            updateHealthScore(predictionMetrics);
        } catch (e) {
            console.warn('Error updating health score:', e);
        }
        
        try {
            updateQuickInsights(predictionMetrics);
        } catch (e) {
            console.warn('Error updating quick insights:', e);
        }
        
        try {
            updateAlerts(predictionMetrics);
        } catch (e) {
            console.warn('Error updating alerts:', e);
        }
        
        try {
            updateBenchmarks(predictionMetrics);
        } catch (e) {
            console.warn('Error updating benchmarks:', e);
        }
        
        try {
            updateRULCountdown(predictionMetrics);
        } catch (e) {
            console.warn('Error updating RUL countdown:', e);
        }
        
        // Update degradation value
        try {
            if (predictionMetrics) {
                const degradation = predictionMetrics.degradation_so_far_pct || 0;
                const degRate = predictionMetrics.degradation_rate_pct_per_month || 0;
                const degValueEl = document.getElementById('degradation-value');
                const degRateEl = document.getElementById('degradation-rate');
                if (degValueEl) degValueEl.textContent = degradation.toFixed(2) + '%';
                if (degRateEl) degRateEl.textContent = `${degRate.toFixed(3)}%/month`;
            }
        } catch (e) {
            console.warn('Error updating degradation:', e);
        }
        
        // Update data points indicator
        updateDataPointsIndicator(history.length, dailySummariesData?.count || null);
        
        // Update charts (pass filtered data)
        console.log('Updating charts with history length:', history.length);
        updateCharts(history, predictionMetrics, dailySummariesData);
    } catch (error) {
        console.error('Error updating dashboard:', error);
    }
}

function updateCharts(history, predictionMetrics, dailySummaries = null) {
    if (history.length === 0) {
        console.warn('No history data to plot');
        return;
    }
    
    console.log('updateCharts called with history length:', history.length, 'time range:', currentTimeRange);
    
    // Filter history based on current time range (if not already filtered by API)
    let filteredHistory = history;
    if (currentTimeRange !== 'all' && history.length > 0) {
        // For relative time data, take the last N points based on range
        const maxPoints = currentTimeRange === '24h' ? Math.min(8640, history.length) : // ~1 point per 10s for 24h
                         currentTimeRange === '7d' ? Math.min(6048, history.length) : // ~1 point per 100s for 7d
                         currentTimeRange === '30d' ? Math.min(2592, history.length) : // ~1 point per 1000s for 30d
                         currentTimeRange === '3m' ? Math.min(2592, history.length) : // Same as 30d
                         history.length; // Default: all
        const originalLength = filteredHistory.length;
        filteredHistory = history.slice(-maxPoints);
        console.log(`Chart filtering: ${originalLength} -> ${filteredHistory.length} points for ${currentTimeRange}`);
    }

    // Chart 1: SOC vs Time (filtered by time range)
    const recentHistory = filteredHistory.slice(-1000); // Last 1000 points from filtered data
    console.log('Plotting SOC chart with', recentHistory.length, 'points');
    const socData = recentHistory.map((h, i) => ({
        x: i,
        soc: (h.soc || 0) * 100,
        time: h.time_s || i
    }));

    const socTrace = {
        x: socData.map(d => d.time),
        y: socData.map(d => d.soc),
        name: 'SOC',
        type: 'scatter',
        mode: 'lines',
        line: { color: '#4A90E2', width: 2 }
    };

    Plotly.newPlot('soc-chart', [socTrace], {
        xaxis: { title: 'Time' },
        yaxis: { title: 'SOC (%)', range: [0, 100] },
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)'
    });

    // Chart 2: SOH Trend (months) - use filtered history
    const sohData = recentHistory.map((h, i) => ({
        x: i,
        soh: ((h.params?.Q_Ah || 2.0) / 2.0) * 100
    }));

    const sohTrace = {
        x: sohData.map(d => d.x),
        y: sohData.map(d => d.soh),
        name: 'SOH',
        type: 'scatter',
        mode: 'lines',
        line: { color: '#50C878', width: 2 }
    };

    Plotly.newPlot('soh-trend-chart', [sohTrace], {
        xaxis: { title: 'Time Index' },
        yaxis: { title: 'SOH (%)', range: [0, 100] },
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)'
    });

    // Chart 3: Temperature & Current Correlation (colored scatter) - use filtered history
    const tempCurrentData = recentHistory.map((h, i) => ({
        temp: h.temp_C || 25.0,
        current: h.I_A || 0.0
    }));

    const tempCurrentTrace = {
        x: tempCurrentData.map(d => d.temp),
        y: tempCurrentData.map(d => d.current),
        mode: 'markers',
        type: 'scatter',
        marker: {
            size: 5,
            color: tempCurrentData.map(d => d.temp),
            colorscale: 'Viridis',
            showscale: true,
            colorbar: { title: 'Temp (°C)' }
        },
        name: 'Temp vs Current'
    };

    Plotly.newPlot('temp-current-chart', [tempCurrentTrace], {
        xaxis: { title: 'Temperature (°C)' },
        yaxis: { title: 'Current (A)' },
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)'
    });

    // Chart 4: SOH Projection (if prediction metrics available)
    if (predictionMetrics && predictionMetrics.current_soh_pct !== undefined) {
        const currentSoh = predictionMetrics.current_soh_pct * 100;
        const degRate = predictionMetrics.degradation_rate_pct_per_month || 0;
        const rulMonths = predictionMetrics.rul_months;
        const degradationTrend = predictionMetrics.degradation_trend || 'stable';
        
        const weeks = [];
        const sohValues = [];
        const traces = [];
        
        // Always show current SOH point
        const currentTrace = {
            x: [0],
            y: [currentSoh],
            name: 'Current SOH',
            type: 'scatter',
            mode: 'markers',
            marker: { size: 12, color: '#50C878' }
        };
        traces.push(currentTrace);
        
        // Create projection if we have degradation
        if (degRate < -0.001 || (degradationTrend !== 'stable' && degradationTrend !== 'improving')) {
            // Battery is degrading - show projection
            for (let i = 0; i <= 24; i++) { // 24 weeks = ~6 months
                weeks.push(i);
                const projectedSoh = Math.max(0, Math.min(100, currentSoh + (degRate * (i / 4.33)))); // Convert weeks to months
                sohValues.push(projectedSoh);
            }
            
            const projectionTrace = {
                x: weeks,
                y: sohValues,
                name: 'Projected SOH',
                type: 'scatter',
                mode: 'lines+markers',
                line: { color: '#FF6B6B', dash: 'dash', width: 2 }
            };
            traces.push(projectionTrace);
        } else {
            // Battery is stable - show flat line indicating no degradation
            for (let i = 0; i <= 24; i++) {
                weeks.push(i);
                sohValues.push(currentSoh);
            }
            
            const stableTrace = {
                x: weeks,
                y: sohValues,
                name: 'Stable SOH (No degradation detected)',
                type: 'scatter',
                mode: 'lines',
                line: { color: '#50C878', width: 2 }
            };
            traces.push(stableTrace);
        }

        Plotly.newPlot('soh-projection-chart', traces, {
            xaxis: { title: 'Weeks from Now' },
            yaxis: { title: 'SOH (%)', range: [0, 100] },
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)',
            legend: { x: 0, y: 1 }
        });
    } else {
        // Fallback: Show empty chart with message
        Plotly.newPlot('soh-projection-chart', [], {
            xaxis: { title: 'Weeks from Now' },
            yaxis: { title: 'SOH (%)', range: [0, 100] },
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)',
            annotations: [{
                text: 'No projection data available',
                xref: 'paper',
                yref: 'paper',
                x: 0.5,
                y: 0.5,
                showarrow: false,
                font: { size: 14, color: '#666' }
            }]
        });
    }
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

// Calculate Health Score (0-100)
function calculateHealthScore(predictionMetrics) {
    if (!predictionMetrics) return null;
    
    let score = 100;
    
    // SOH contribution (40 points)
    const soh = predictionMetrics.current_soh_pct || 1.0;
    const sohScore = soh * 40;
    
    // Degradation contribution (30 points) - lower degradation = higher score
    const degradation = Math.abs(predictionMetrics.degradation_so_far_pct || 0);
    const degScore = Math.max(0, 30 - (degradation * 1.5)); // -1.5 points per % degradation
    
    // Thermal stress contribution (20 points) - lower stress = higher score
    const thermalStress = predictionMetrics.thermal_stress_index || 0;
    const thermalScore = Math.max(0, 20 - (thermalStress / 50)); // Normalize thermal stress
    
    // Charging habits contribution (10 points)
    const habitScore = predictionMetrics.recharge_habit_score || 0;
    const habitPoints = Math.min(10, habitScore * 10);
    
    score = sohScore + degScore + thermalScore + habitPoints;
    return Math.max(0, Math.min(100, Math.round(score)));
}

// Update Health Score Hero Section
function updateHealthScore(predictionMetrics) {
    const score = calculateHealthScore(predictionMetrics);
    if (score === null) return;
    
    // Check if elements exist
    const scoreValueEl = document.getElementById('health-score-value');
    const circle = document.getElementById('health-score-circle');
    const heroCard = document.getElementById('health-score-hero');
    const statusText = document.getElementById('health-status-text');
    const summaryText = document.getElementById('health-summary-text');
    
    if (!scoreValueEl || !circle || !heroCard || !statusText || !summaryText) {
        return; // Elements don't exist, skip
    }
    
    // Update score value
    scoreValueEl.textContent = score;
    
    // Update circle gradient
    circle.style.setProperty('--health-score', score);
    
    let status, className, summary;
    if (score >= 90) {
        status = '🟢 Excellent';
        className = 'excellent';
        summary = 'Your battery is performing exceptionally well with minimal degradation.';
    } else if (score >= 75) {
        status = '🔵 Good';
        className = 'good';
        summary = 'Your battery is in good condition. Continue monitoring for optimal performance.';
    } else if (score >= 60) {
        status = '🟡 Fair';
        className = 'fair';
        summary = 'Your battery shows some signs of wear. Consider optimizing charging habits.';
    } else {
        status = '🔴 Poor';
        className = 'poor';
        summary = 'Your battery requires attention. Review charging patterns and consider maintenance.';
    }
    
    statusText.textContent = status;
    summaryText.textContent = summary;
    heroCard.className = `card ${className}`;
    
    // Update breakdown
    const soh = (predictionMetrics.current_soh_pct || 1.0) * 100;
    const degradation = Math.abs(predictionMetrics.degradation_so_far_pct || 0);
    const thermal = predictionMetrics.thermal_stress_index || 0;
    
    const sohBar = document.getElementById('breakdown-soh');
    const sohValue = document.getElementById('breakdown-soh-value');
    const degBar = document.getElementById('breakdown-deg');
    const degValue = document.getElementById('breakdown-deg-value');
    const thermalBar = document.getElementById('breakdown-thermal');
    const thermalValue = document.getElementById('breakdown-thermal-value');
    
    if (sohBar) sohBar.style.width = soh + '%';
    if (sohValue) sohValue.textContent = soh.toFixed(1) + '%';
    
    const degPercent = Math.max(0, 100 - (degradation * 5));
    if (degBar) degBar.style.width = degPercent + '%';
    if (degValue) degValue.textContent = degradation.toFixed(2) + '%';
    
    const thermalPercent = Math.max(0, 100 - (thermal / 10));
    if (thermalBar) thermalBar.style.width = thermalPercent + '%';
    if (thermalValue) thermalValue.textContent = thermal.toFixed(1);
}

// Update Quick Insights
function updateQuickInsights(predictionMetrics) {
    const insights = [];
    
    if (predictionMetrics) {
        const soh = (predictionMetrics.current_soh_pct || 1.0) * 100;
        const degradation = predictionMetrics.degradation_so_far_pct || 0;
        const rangeLoss = predictionMetrics.range_loss_km || 0;
        const thermalStress = predictionMetrics.thermal_stress_index || 0;
        const chargeEff = (predictionMetrics.charge_efficiency_trend || 1.0) * 100;
        const rulMonths = predictionMetrics.rul_months;
        
        insights.push({
            icon: soh >= 95 ? '✅' : soh >= 80 ? '⚠️' : '🔴',
            text: `Battery health is ${soh >= 95 ? 'excellent' : soh >= 80 ? 'good' : 'fair'} (${soh.toFixed(1)}% SOH)`
        });
        
        if (degradation === 0) {
            insights.push({
                icon: '✅',
                text: `No degradation detected (${degradation.toFixed(2)}% loss)`
            });
        } else {
            insights.push({
                icon: degradation < 5 ? '⚠️' : '🔴',
                text: `Degradation: ${degradation.toFixed(2)}% (${degradation < 5 ? 'normal' : 'monitor'})`
            });
        }
        
        if (rangeLoss === 0) {
            insights.push({
                icon: '✅',
                text: `Range loss: 0 km (excellent)`
            });
        } else {
            insights.push({
                icon: '⚠️',
                text: `Range loss: ${rangeLoss.toFixed(0)} km from new`
            });
        }
        
        if (thermalStress > 1000) {
            insights.push({
                icon: '⚠️',
                text: `Thermal stress: ${thermalStress.toFixed(0)} hours (monitor)`
            });
        } else {
            insights.push({
                icon: '✅',
                text: `Thermal stress: ${thermalStress.toFixed(0)} hours (normal)`
            });
        }
        
        insights.push({
            icon: chargeEff >= 90 ? '✅' : '⚠️',
            text: `Charging efficiency: ${chargeEff.toFixed(1)}%`
        });
        
        if (rulMonths !== null && rulMonths !== undefined) {
            insights.push({
                icon: rulMonths > 24 ? '✅' : rulMonths > 12 ? '⚠️' : '🔴',
                text: `Remaining life: ${rulMonths.toFixed(1)} months`
            });
        } else {
            insights.push({
                icon: '✅',
                text: `Battery not degrading (stable)`
            });
        }
    } else {
        insights.push({
            icon: '⏳',
            text: 'Loading prediction metrics...'
        });
    }
    
    const insightsList = document.getElementById('quick-insights');
    if (insightsList) {
        insightsList.innerHTML = insights.map(insight => 
            `<li><span class="insight-icon">${insight.icon}</span> <span class="insight-text">${insight.text}</span></li>`
        ).join('');
    }
}

// Update Alerts
function updateAlerts(predictionMetrics) {
    const container = document.getElementById('alert-container');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (!predictionMetrics) return;
    
    const alerts = [];
    const degradation = predictionMetrics.degradation_so_far_pct || 0;
    const degRate = predictionMetrics.degradation_rate_pct_per_month || 0;
    const thermalStress = predictionMetrics.thermal_stress_index || 0;
    const chargeEff = (predictionMetrics.charge_efficiency_trend || 1.0) * 100;
    
    // Critical alerts
    if (degradation > 20) {
        alerts.push({
            level: 'danger',
            title: 'High Degradation Detected',
            message: `Battery has lost ${degradation.toFixed(2)}% capacity. Consider maintenance.`
        });
    }
    
    if (thermalStress > 1500) {
        alerts.push({
            level: 'warning',
            title: 'High Thermal Stress',
            message: `Thermal stress index is ${thermalStress.toFixed(0)}. Consider reducing fast charging.`
        });
    }
    
    if (chargeEff < 85) {
        alerts.push({
            level: 'warning',
            title: 'Low Charging Efficiency',
            message: `Charging efficiency is ${chargeEff.toFixed(1)}%. Check charging equipment.`
        });
    }
    
    // Info alerts
    if (degradation === 0 && degRate === 0) {
        alerts.push({
            level: 'success',
            title: 'Battery Health Excellent',
            message: 'No degradation detected. Battery is performing optimally.'
        });
    }
    
    // Render alerts
    alerts.forEach(alert => {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert-banner ${alert.level}`;
        alertDiv.innerHTML = `
            <div class="alert-content">
                <div class="alert-title">${alert.title}</div>
                <div class="alert-message">${alert.message}</div>
            </div>
            <button class="alert-close" onclick="this.parentElement.remove()">&times;</button>
        `;
        container.appendChild(alertDiv);
    });
}

// Update Trend Indicators
function updateTrendIndicator(elementId, currentValue, previousValue, isPercentage = false) {
    const element = document.getElementById(elementId);
    if (!element || previousValue === null || previousValue === undefined) {
        element.className = 'trend-indicator stable';
        return;
    }
    
    const change = currentValue - previousValue;
    const threshold = isPercentage ? 0.1 : (currentValue * 0.01); // 1% change threshold
    
    if (Math.abs(change) < threshold) {
        element.className = 'trend-indicator stable';
    } else if (change > 0) {
        element.className = 'trend-indicator up';
    } else {
        element.className = 'trend-indicator down';
    }
}

// Update Benchmarks
function updateBenchmarks(predictionMetrics) {
    if (!predictionMetrics) return;
    
    const soh = (predictionMetrics.current_soh_pct || 1.0) * 100;
    const range = predictionMetrics.current_range_km || 400;
    const temp = 25; // Will be updated from daily summaries
    
    // SOH benchmark
    const sohBenchmark = document.getElementById('soh-benchmark');
    if (sohBenchmark) {
        if (soh >= 95) {
            sohBenchmark.textContent = '⭐ Excellent (95-100%)';
            sohBenchmark.style.color = 'var(--success)';
        } else if (soh >= 80) {
            sohBenchmark.textContent = '✓ Good (80-95%)';
            sohBenchmark.style.color = 'var(--info)';
        } else {
            sohBenchmark.textContent = '⚠ Monitor (<80%)';
            sohBenchmark.style.color = 'var(--warning)';
        }
    }
    
    // Range benchmark
    const rangeBenchmark = document.getElementById('range-benchmark');
    if (rangeBenchmark) {
        const rangeLoss = predictionMetrics.range_loss_km || 0;
        if (rangeLoss === 0) {
            rangeBenchmark.textContent = '⭐ No range loss';
            rangeBenchmark.style.color = 'var(--success)';
        } else if (rangeLoss < 20) {
            rangeBenchmark.textContent = '✓ Minimal loss';
            rangeBenchmark.style.color = 'var(--info)';
        } else {
            rangeBenchmark.textContent = '⚠ Significant loss';
            rangeBenchmark.style.color = 'var(--warning)';
        }
    }
    
    // Temperature benchmark
    const tempBenchmark = document.getElementById('temp-benchmark');
    if (tempBenchmark) {
        if (temp >= 20 && temp <= 30) {
            tempBenchmark.textContent = '⭐ Optimal (20-30°C)';
            tempBenchmark.style.color = 'var(--success)';
        } else if (temp >= 15 && temp <= 35) {
            tempBenchmark.textContent = '✓ Good (15-35°C)';
            tempBenchmark.style.color = 'var(--info)';
        } else {
            tempBenchmark.textContent = '⚠ Monitor';
            tempBenchmark.style.color = 'var(--warning)';
        }
    }
}

// Update RUL Countdown
function updateRULCountdown(predictionMetrics) {
    const rulMonths = predictionMetrics?.rul_months;
    const rulConfidence = predictionMetrics?.rul_confidence || 0;
    const rulStatus = predictionMetrics?.rul_status || 'not_degrading';
    
    const rulValueMain = document.getElementById('rul-value-main');
    const rulConfidenceMain = document.getElementById('rul-confidence-main');
    const rulStatusMain = document.getElementById('rul-status-main');
    const rulProgressBar = document.getElementById('rul-progress-bar');
    
    if (!rulValueMain || !rulConfidenceMain || !rulStatusMain || !rulProgressBar) {
        return; // Elements don't exist
    }
    
    if (rulMonths !== null && rulMonths !== undefined) {
        let rulText;
        if (rulMonths > 12) {
            rulText = `${(rulMonths/12).toFixed(1)}y`;
        } else if (rulMonths >= 1) {
            rulText = `${rulMonths.toFixed(0)}mo`;
        } else {
            rulText = `${(rulMonths*30).toFixed(0)}d`;
        }
        rulValueMain.textContent = rulText;
        rulConfidenceMain.textContent = `${(rulConfidence * 100).toFixed(0)}% confidence`;
        
        // Progress bar (assuming 10 years = 120 months as full life)
        const progressPercent = Math.min(100, (rulMonths / 120) * 100);
        rulProgressBar.style.width = progressPercent + '%';
        
        if (rulMonths > 60) {
            rulStatusMain.textContent = '🟢 Excellent';
            rulStatusMain.style.color = 'var(--success)';
        } else if (rulMonths > 24) {
            rulStatusMain.textContent = '🔵 Good';
            rulStatusMain.style.color = 'var(--info)';
        } else if (rulMonths > 12) {
            rulStatusMain.textContent = '🟡 Fair';
            rulStatusMain.style.color = 'var(--warning)';
        } else {
            rulStatusMain.textContent = '🔴 Monitor';
            rulStatusMain.style.color = 'var(--danger)';
        }
    } else {
        rulValueMain.textContent = 'N/A';
        rulConfidenceMain.textContent = rulStatus.replace('_', ' ');
        rulProgressBar.style.width = '100%';
        rulStatusMain.textContent = '✅ Not degrading';
        rulStatusMain.style.color = 'var(--success)';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    updateDashboard();
    updateFetchStatus();
    
    // Time range selector (if it exists)
    const timeRangeButtons = document.querySelectorAll('#time-range-selector button');
    if (timeRangeButtons.length > 0) {
        timeRangeButtons.forEach(btn => {
            btn.addEventListener('click', function() {
                timeRangeButtons.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                const range = this.dataset.range;
                const oldRange = currentTimeRange;
                currentTimeRange = range;
                console.log('Time range changed:', oldRange, '->', range);
                const dateRange = getDateRange(range, dataDateRange);
                console.log('Date range will be:', dateRange);
                // Show loading state
                const indicator = document.getElementById('data-points-indicator');
                if (indicator) indicator.textContent = 'Loading...';
                // Force update
                updateDashboard();
            });
        });
    } else {
        console.warn('Time range selector buttons not found');
    }
    
    // Update every 5 seconds
    updateInterval = setInterval(updateDashboard, 5000);
    
    // Fetch button (if it exists)
    const fetchBtn = document.getElementById('fetch-btn');
    if (fetchBtn) {
        fetchBtn.addEventListener('click', async function() {
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
    }
});
