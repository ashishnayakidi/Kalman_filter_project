"""Streamlit frontend application for battery monitoring dashboard."""
import streamlit as st
from pathlib import Path
import sys

# Add parent directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Page configuration
st.set_page_config(
    page_title="Battery Health Monitor",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = False

# Import shared utilities
from frontend.utils import initialize_app

# Initialize app on first run
if not st.session_state.initialized:
    initialize_app()
    st.session_state.initialized = True

# Main landing page
st.title("🔋 Battery Health Monitor")
st.markdown("Real-time monitoring of State of Charge (SOC) and State of Health (SOH)")

st.info("💡 Use the sidebar to navigate to **Dashboard**, **Chat**, or **Reports** pages")

st.markdown("""
### Quick Start

1. **Dashboard**: View real-time metrics, charts, and health insights
2. **Chat**: Ask questions about your battery's health using AI
3. **Reports**: Generate weekly battery health reports

### Features

- ⚡ Real-time SOC/SOH monitoring
- 📊 Interactive charts and visualizations
- 💬 AI-powered Q&A about battery health
- 📋 Weekly health reports
- 🔄 Automatic data fetching (every hour)
""")
