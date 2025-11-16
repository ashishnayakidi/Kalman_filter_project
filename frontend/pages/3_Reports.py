"""Weekly reports page."""
import streamlit as st
from datetime import datetime

from frontend.utils import get_scorer_instance, get_lfm
from agent.scoring import daily_summary
from lfm.prompts import build_weekly_report_prompt

st.set_page_config(page_title="Reports", layout="wide")

st.title("📋 Weekly Battery Health Report")
st.markdown("AI-generated weekly summary of your battery's health and performance")

if st.button("Generate Weekly Report", type="primary"):
    with st.spinner("Generating report..."):
        try:
            scorer = get_scorer_instance()
            daily = scorer.daily_summary()
            
            # Try to use LFM
            lfm = get_lfm()
            if lfm is None:
                st.warning("AI model not available. Showing basic summary.")
                
                # Basic report
                soh = daily.get('soh_pct', 100.0)
                st.markdown("### Summary")
                st.markdown(f"**State of Health**: {soh:.1f}%")
                
                dcir_changes = daily.get('dcir_changes', {})
                if dcir_changes:
                    st.markdown("### DCIR Changes")
                    for key, val in dcir_changes.items():
                        change = val.get('rel_change_pct', 0)
                        soc_label = key.replace('soc_', 'SOC ').replace('_', ' ').upper()
                        st.markdown(f"- **{soc_label}**: {change:+.1f}% change")
                
                stress = daily.get('stress', {})
                if stress:
                    st.markdown("### Stress Metrics")
                    st.markdown(f"- Fast Charge Hours: {stress.get('fast_charge_hours', 0):.1f}h")
                    st.markdown(f"- High Temp Hours: {stress.get('high_temp_hours', 0):.1f}h")
                    st.markdown(f"- High SOC Hours: {stress.get('high_soc_hours', 0):.1f}h")
            else:
                # Generate AI report
                prompt = build_weekly_report_prompt(daily)
                report = lfm.generate(prompt, max_tokens=1024)
                
                st.markdown("### Weekly Report")
                st.markdown(report)
                
                st.markdown("---")
                st.markdown("### Detailed Metrics")
                st.json(daily)
        except Exception as e:
            st.error(f"Error generating report: {e}")
            import traceback
            st.code(traceback.format_exc())

# Show last report time
if "last_report_time" in st.session_state:
    st.caption(f"Last generated: {st.session_state.last_report_time}")

