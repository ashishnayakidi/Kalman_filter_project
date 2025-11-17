"""Fleet Monitoring Console - Streamlit App."""
import streamlit as st
import sys
from pathlib import Path
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta

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

st.set_page_config(
    page_title="Fleet Monitoring Console",
    page_icon="🚗",
    layout="wide"
)

st.title("🚗 Fleet Monitoring Console")
st.markdown("**OEM & Fleet Manager Dashboard** - Monitor thousands of batteries in real-time")

# Sidebar filters
st.sidebar.header("Filters")
region_filter = st.sidebar.selectbox(
    "Region",
    ["All"] + list(set(v.region for v in get_all_vehicles() if v.region != "Unknown"))
)

model_filter = st.sidebar.selectbox(
    "Vehicle Model",
    ["All"] + list(set(v.model for v in get_all_vehicles() if v.model != "Unknown"))
)

# Main tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🗺️ Map View",
    "📊 Fleet Overview",
    "⚠️ Alerts & Ranking",
    "📈 Analytics",
    "🎯 Lead Generation"
])

with tab1:
    st.header("Vehicle Map View")
    
    vehicles = get_all_vehicles()
    latest_states = get_all_latest_states()
    
    # Filter vehicles
    if region_filter != "All":
        vehicles = [v for v in vehicles if v.region == region_filter]
    if model_filter != "All":
        vehicles = [v for v in vehicles if v.model == model_filter]
    
    if not vehicles:
        st.info("No vehicles found. Ingest some telematics data to see vehicles on the map.")
    else:
        # Create map data
        map_data = []
        for vehicle in vehicles:
            state = latest_states.get(vehicle.vin)
            if not state:
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
            
            if vehicle.latitude and vehicle.longitude:
                map_data.append({
                    'vin': vehicle.vin,
                    'model': vehicle.model,
                    'soh': state.soh,
                    'status': status,
                    'lat': vehicle.latitude,
                    'lon': vehicle.longitude
                })
        
        if map_data:
            df_map = pd.DataFrame(map_data)
            
            # Create map
            fig = px.scatter_mapbox(
                df_map,
                lat='lat',
                lon='lon',
                hover_name='vin',
                hover_data=['model', 'soh', 'status'],
                color='soh',
                color_continuous_scale='RdYlGn',
                range_color=[0, 100],
                zoom=2,
                height=600
            )
            fig.update_layout(mapbox_style="open-street-map")
            st.plotly_chart(fig, use_container_width=True)
            
            # Summary
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Vehicles", len(vehicles))
            with col2:
                green_count = sum(1 for d in map_data if d['soh'] >= 90)
                st.metric("🟢 Excellent", green_count)
            with col3:
                yellow_count = sum(1 for d in map_data if 80 <= d['soh'] < 90)
                st.metric("🟡 Good", yellow_count)
            with col4:
                red_count = sum(1 for d in map_data if d['soh'] < 80)
                st.metric("🔴 Poor", red_count)
        else:
            st.warning("No vehicles with location data. Add latitude/longitude to telematics data.")

with tab2:
    st.header("Fleet Health Overview")
    
    overview = get_fleet_health_overview()
    regional_stats = get_regional_stats()
    
    if overview['total_vehicles'] == 0:
        st.info("No vehicles in fleet. Ingest telematics data to see fleet health.")
    else:
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Vehicles", overview['total_vehicles'])
        with col2:
            st.metric("Average SOH", f"{overview['avg_soh']:.1f}%")
        with col3:
            st.metric("Avg Degradation", f"{overview['avg_degradation_rate']:.2f}%/month")
        with col4:
            st.metric("Vehicles at Risk", overview['vehicles_at_risk'])
        
        # SOH Distribution
        st.subheader("SOH Distribution")
        dist = overview['soh_distribution']
        fig = go.Figure(data=[
            go.Bar(
                x=['Excellent (≥90%)', 'Good (80-90%)', 'Fair (70-80%)', 'Poor (<70%)'],
                y=[dist['excellent'], dist['good'], dist['fair'], dist['poor']],
                marker_color=['green', 'yellow', 'orange', 'red']
            )
        ])
        fig.update_layout(title="Battery Health Distribution", yaxis_title="Number of Vehicles")
        st.plotly_chart(fig, use_container_width=True)
        
        # Regional Stats
        if regional_stats:
            st.subheader("Regional Statistics")
            df_regional = pd.DataFrame([
                {'Region': region, 'Vehicles': stats['vehicles'], 'Avg SOH': stats['avg_soh']}
                for region, stats in regional_stats.items()
            ])
            st.dataframe(df_regional, use_container_width=True)

with tab3:
    st.header("Alerts & Ranking")
    
    # Vehicles at Risk
    st.subheader("Vehicles at Risk (Ranked)")
    at_risk = get_vehicles_at_risk(limit=50)
    
    if at_risk:
        df_risk = pd.DataFrame(at_risk)
        st.dataframe(
            df_risk[['vin', 'model', 'region', 'soh', 'degradation_rate', 'rul_days', 'risk_score']],
            use_container_width=True
        )
    else:
        st.info("No vehicles at risk.")
    
    # Recent Alerts
    st.subheader("Recent Alerts")
    alerts = get_alerts(severity=None, resolved=False)
    
    if alerts:
        # Group by severity
        critical = [a for a in alerts if a.severity == 'critical']
        high = [a for a in alerts if a.severity == 'high']
        medium = [a for a in alerts if a.severity == 'medium']
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🔴 Critical", len(critical))
        with col2:
            st.metric("🟠 High", len(high))
        with col3:
            st.metric("🟡 Medium", len(medium))
        
        # Show recent alerts
        for alert in alerts[:20]:
            severity_color = {
                'critical': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🟢'
            }.get(alert.severity, '⚪')
            
            st.markdown(f"""
            **{severity_color} {alert.alert_type.upper()}** - VIN: `{alert.vin}`  
            {alert.message}  
            *{alert.created_at}*
            """)
    else:
        st.info("No active alerts.")

with tab4:
    st.header("Analytics & Trends")
    
    # Historical Trends
    st.subheader("Fleet Average SOH Trend (Last 90 Days)")
    trends = get_historical_trends(days=90)
    
    if trends.get('dates') and trends.get('avg_soh'):
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trends['dates'],
            y=trends['avg_soh'],
            mode='lines+markers',
            name='Fleet Average SOH'
        ))
        fig.update_layout(
            title="Fleet Average SOH Over Time",
            xaxis_title="Date",
            yaxis_title="SOH (%)",
            yaxis_range=[0, 100]
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Insufficient data for trend analysis.")
    
    # Usage Clusters
    st.subheader("Usage Clusters")
    clusters = get_usage_clusters()
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**High Fast Charge Usage**")
        if clusters['high_fast_charge']:
            df_fast = pd.DataFrame(clusters['high_fast_charge'])
            st.dataframe(df_fast, use_container_width=True)
        else:
            st.info("No vehicles with high fast charge usage.")
    
    with col2:
        st.write("**High Temperature Exposure**")
        if clusters['high_temp']:
            df_temp = pd.DataFrame(clusters['high_temp'])
            st.dataframe(df_temp, use_container_width=True)
        else:
            st.info("No vehicles with high temperature exposure.")
    
    # Failure Predictions
    st.subheader("Failure Predictions")
    predictions = predict_failures()
    
    if predictions:
        df_pred = pd.DataFrame(predictions)
        st.dataframe(df_pred, use_container_width=True)
    else:
        st.info("No failure predictions at this time.")

with tab5:
    st.header("Lead Generation Engine")
    
    st.markdown("**Vehicles Due for Pack Replacement or Upgrade**")
    
    candidates = get_lead_generation_candidates()
    
    if candidates:
        df_leads = pd.DataFrame(candidates)
        
        # Priority filter
        priority_filter = st.selectbox("Priority", ["All", "High", "Medium"])
        if priority_filter != "All":
            df_leads = df_leads[df_leads['priority'] == priority_filter.lower()]
        
        st.dataframe(df_leads, use_container_width=True)
        
        # Summary
        st.subheader("Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Candidates", len(candidates))
        with col2:
            high_priority = sum(1 for c in candidates if c['priority'] == 'high')
            st.metric("High Priority", high_priority)
        with col3:
            avg_soh = sum(c['soh'] for c in candidates) / len(candidates) if candidates else 0
            st.metric("Average SOH", f"{avg_soh:.1f}%")
    else:
        st.info("No lead generation candidates at this time.")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**Fleet Console v0.1.0**")
st.sidebar.markdown("Powered by EKF + LFM2-350M")


