"""Dashboard page for battery monitoring."""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import pandas as pd

from frontend.utils import (
    get_ekf, get_scorer_instance, fetch_and_process_data, get_fetch_status
)
from agent.scoring import daily_summary, minute_rollup

# Page config
st.set_page_config(page_title="Dashboard", layout="wide")

st.title("📊 Battery Health Dashboard")
st.markdown("Real-time monitoring of State of Charge (SOC) and State of Health (SOH)")

# Fetch button and status
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("### Current Status")
with col2:
    if st.button("🔄 Fetch Latest Data", width='stretch'):
        with st.spinner("Fetching data..."):
            success = fetch_and_process_data(force=True)
            if success:
                st.success("Data fetched successfully!")
                st.rerun()
            else:
                st.warning("Data fetch completed (may have been skipped)")

# Fetch status
fetch_status = get_fetch_status()
if fetch_status['last_fetch_time']:
    fetch_time = datetime.fromisoformat(fetch_status['last_fetch_time'])
    hours_ago = fetch_status['time_since_fetch_hours']
    if hours_ago < 1:
        time_str = f"{int(hours_ago * 60)} minutes ago"
    elif hours_ago < 24:
        time_str = f"{hours_ago:.1f} hours ago"
    else:
        time_str = f"{int(hours_ago / 24)} days ago"
    st.caption(f"Last fetched: {fetch_time.strftime('%Y-%m-%d %H:%M:%S')} ({time_str})")

try:
    ekf = get_ekf()
    scorer = get_scorer_instance()
    state = ekf.get_state()
    daily = scorer.daily_summary()
    minute = minute_rollup()
    
    # Calculate SOH
    Q_current = state['params']['Q_Ah']
    Q_nominal = 2.0  # From config
    soh = (Q_current / Q_nominal) * 100 if Q_nominal > 0 else 100.0
    soc = state['soc'] * 100
    
    # Get history data (needed for voltage metric and charts)
    history = ekf.history[-1000:] if len(ekf.history) > 0 else []
    
    # Key Metrics
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("State of Charge (SOC)", f"{soc:.1f}%", delta=None)
        st.progress(soc / 100)
    
    with col2:
        st.metric("State of Health (SOH)", f"{soh:.1f}%", delta=None)
        st.progress(soh / 100)
    
    with col3:
        # Get voltage from history if available, otherwise use state
        if len(history) > 0 and 'v_pred' in history[-1]:
            v_pred = history[-1].get('v_pred', history[-1].get('V_V', 3.7))
        else:
            v_pred = state.get('v_pred', 3.7)
        st.metric("Voltage", f"{v_pred:.3f} V")
    
    with col4:
        temp = daily.get('avg_temp_C', 25.0)
        st.metric("Temperature", f"{temp:.1f}°C")
    
    # Charts
    st.markdown("---")
    st.markdown("### Charts")
    
    if len(history) > 0:
        # Prepare data
        df_history = pd.DataFrame(history)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### SOC & SOH Over Time")
            if 'soc' in df_history.columns:
                fig_soc = go.Figure()
                fig_soc.add_trace(go.Scatter(
                    y=df_history['soc'].values * 100,
                    mode='lines',
                    name='SOC (%)',
                    line=dict(color='#3b82f6')
                ))
                fig_soc.update_layout(
                    height=300,
                    xaxis_title="Sample",
                    yaxis_title="SOC (%)",
                    showlegend=True
                )
                st.plotly_chart(fig_soc, use_container_width=True)
            else:
                st.info("No SOC data available")
        
        with col2:
            st.markdown("#### Voltage & Residual")
            if 'v_pred' in df_history.columns or 'V_V' in df_history.columns:
                fig_voltage = go.Figure()
                voltage_data = df_history.get('v_pred', df_history.get('V_V', []))
                if len(voltage_data) > 0:
                    fig_voltage.add_trace(go.Scatter(
                        y=voltage_data.values,
                        mode='lines',
                        name='Voltage (V)',
                        line=dict(color='#10b981')
                    ))
                if 'residual' in df_history.columns:
                    fig_voltage.add_trace(go.Scatter(
                        y=df_history['residual'].values * 1000,
                        mode='lines',
                        name='Residual (mV)',
                        yaxis='y2',
                        line=dict(color='#ef4444')
                    ))
                    fig_voltage.update_layout(
                        height=300,
                        xaxis_title="Sample",
                        yaxis_title="Voltage (V)",
                        yaxis2=dict(title="Residual (mV)", overlaying="y", side="right"),
                        showlegend=True
                    )
                else:
                    fig_voltage.update_layout(
                        height=300,
                        xaxis_title="Sample",
                        yaxis_title="Voltage (V)",
                        showlegend=True
                    )
                st.plotly_chart(fig_voltage, use_container_width=True)
            else:
                st.info("No voltage data available")
    else:
        st.info("No historical data available. Process some data through the EKF to see charts.")
    
    # Insights
    st.markdown("---")
    st.markdown("### Health Insights")
    
    # DCIR Status
    dcir_changes = daily.get('dcir_changes', {})
    if dcir_changes:
        st.markdown("#### DCIR Status")
        for key, val in dcir_changes.items():
            change = val.get('rel_change_pct', 0)
            current = val.get('current_mohm', 0)
            baseline = val.get('baseline_mohm', 0)
            soc_label = key.replace('soc_', 'SOC ').replace('_', ' ').upper()
            
            if abs(change) > 20:
                status_color = "🔴"
            elif abs(change) > 10:
                status_color = "🟡"
            else:
                status_color = "🟢"
            
            st.markdown(f"""
            **{soc_label}**: {status_color} {change:+.1f}% change
            - Current: {current:.1f} mΩ | Baseline: {baseline:.1f} mΩ
            """)
    else:
        st.info("DCIR tracking will appear after processing battery data.")
    
    # Stress metrics
    st.markdown("#### Stress Metrics")
    stress = daily.get('stress', {})
    if stress:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Fast Charge Hours", f"{stress.get('fast_charge_hours', 0):.1f}h")
        with col2:
            st.metric("High Temp Hours", f"{stress.get('high_temp_hours', 0):.1f}h")
        with col3:
            st.metric("High SOC Hours", f"{stress.get('high_soc_hours', 0):.1f}h")
    
except Exception as e:
    st.error(f"Error loading dashboard: {e}")
    import traceback
    st.code(traceback.format_exc())

