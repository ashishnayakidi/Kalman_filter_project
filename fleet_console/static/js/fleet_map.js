// Fleet Map View
let map;
let markers = [];

async function loadMapData() {
    try {
        const response = await fetch('/api/fleet/map_data');
        const data = await response.json();
        
        if (data.error) {
            console.error('Error loading map data:', data.error);
            return;
        }
        
        const mapData = data.map_data || [];
        
        // Update summary
        document.getElementById('total-vehicles').textContent = mapData.length;
        const excellent = mapData.filter(v => v.soh >= 90).length;
        const good = mapData.filter(v => v.soh >= 80 && v.soh < 90).length;
        const poor = mapData.filter(v => v.soh < 80).length;
        
        document.getElementById('excellent-count').textContent = excellent;
        document.getElementById('good-count').textContent = good;
        document.getElementById('poor-count').textContent = poor;
        
        // Create map if not exists
        if (!map) {
            // Use OpenStreetMap with Leaflet (or Plotly mapbox)
            const centerLat = mapData.length > 0 ? 
                mapData.reduce((sum, v) => sum + v.lat, 0) / mapData.length : 37.7749;
            const centerLon = mapData.length > 0 ?
                mapData.reduce((sum, v) => sum + v.lon, 0) / mapData.length : -122.4194;
            
            // Use Plotly scatter mapbox
            const trace = {
                type: 'scattermapbox',
                mode: 'markers',
                lat: mapData.map(v => v.lat),
                lon: mapData.map(v => v.lon),
                text: mapData.map(v => `${v.vin}<br>${v.model}<br>SOH: ${v.soh.toFixed(1)}%`),
                marker: {
                    size: 10,
                    color: mapData.map(v => v.soh),
                    colorscale: 'RdYlGn',
                    cmin: 0,
                    cmax: 100,
                    showscale: true,
                    colorbar: { title: 'SOH (%)' }
                }
            };
            
            const layout = {
                mapbox: { style: 'open-street-map', zoom: 2, center: { lat: centerLat, lon: centerLon } },
                height: 600,
                margin: { l: 0, r: 0, t: 0, b: 0 }
            };
            
            Plotly.newPlot('map-container', [trace], layout, { mapboxAccessToken: '' });
        }
        
    } catch (error) {
        console.error('Error loading map:', error);
    }
}

// Load on page load
document.addEventListener('DOMContentLoaded', function() {
    loadMapData();
    setInterval(loadMapData, 30000); // Refresh every 30 seconds
});


