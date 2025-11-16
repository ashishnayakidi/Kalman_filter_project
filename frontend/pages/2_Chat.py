"""Chat page for Q&A about battery health."""
import streamlit as st
from datetime import datetime

from frontend.utils import get_ekf, get_scorer_instance, get_lfm
from agent.scoring import daily_summary, minute_rollup
from lfm.prompts import build_qna_prompt

st.set_page_config(page_title="Chat", layout="wide")

st.title("💬 Battery Health Chat")
st.markdown("Ask questions about your battery's health and get AI-powered insights")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask a question about battery health..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Get current data
                scorer = get_scorer_instance()
                daily = scorer.daily_summary()
                minute = minute_rollup()
                ekf = get_ekf()
                state = ekf.get_state()
                
                # Try to use LFM (force re-check if None)
                lfm = get_lfm()
                if lfm is None:
                    # Try to reset and check again
                    import frontend.utils.core as core_module
                    core_module._lfm_instance = None
                    lfm = get_lfm()
                
                if lfm is None:
                    # Fallback: Basic answer
                    soh = daily.get('soh_pct', 100.0)
                    soc = state.get('soc', 0.5) * 100
                    answer = f"""Based on your current battery status:

- **State of Charge (SOC)**: {soc:.1f}%
- **State of Health (SOH)**: {soh:.1f}%

"""
                    if 'health' in prompt.lower() or 'soh' in prompt.lower():
                        if soh >= 90:
                            answer += "Your battery health is excellent. Continue normal usage patterns."
                        elif soh >= 80:
                            answer += "Your battery health is good. Monitor for any degradation trends."
                        else:
                            answer += "Your battery health is declining. Consider reducing fast charging and high temperature exposure."
                    elif 'charge' in prompt.lower() or 'soc' in prompt.lower():
                        answer += f"Current charge level is {soc:.1f}%. "
                        if soc < 20:
                            answer += "Consider charging soon to avoid deep discharge."
                        elif soc > 80:
                            answer += "Battery is well charged."
                        else:
                            answer += "Battery charge level is moderate."
                    else:
                        answer += "For detailed AI-powered analysis, please install the LFM2-350M model at models/LFM2-350M-Q4_K_M.gguf"
                    
                    st.markdown(answer)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer
                    })
                else:
                    # Use LFM
                    try:
                        prompt_text = build_qna_prompt(prompt, daily, minute)
                        # Debug: show that we're using LFM
                        model_name = lfm.model_name if hasattr(lfm, 'model_name') else 'Ollama'
                        st.info(f"🤖 Using AI model: {model_name}")
                        
                        # Generate response with progress
                        with st.spinner("Generating AI response (this may take 10-30 seconds)..."):
                            answer = lfm.generate(prompt_text, max_tokens=512)
                        
                        # Check if we got a valid response
                        if not answer or len(answer.strip()) == 0:
                            # Empty response - use fallback
                            soh = daily.get('soh_pct', 100.0)
                            soc = state.get('soc', 0.5) * 100
                            answer = f"""Based on your current battery status:

- **State of Charge (SOC)**: {soc:.1f}%
- **State of Health (SOH)**: {soh:.1f}%

The AI model returned an empty response. Here's a basic answer based on your battery data."""
                            if 'charge' in prompt.lower() or 'charging' in prompt.lower():
                                answer += "\n\n**General Charging Habits:**\n- Avoid keeping battery at 100% for extended periods\n- Try to keep charge between 20-80% for optimal health\n- Avoid deep discharges below 20%\n- Charge at moderate temperatures (20-25°C)\n- Avoid fast charging when not necessary"
                        
                        # Display the answer
                        if answer and len(answer.strip()) > 0:
                            st.markdown(answer)
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": answer
                            })
                        else:
                            raise ValueError("Empty response from AI model")
                    except Exception as gen_error:
                        # Generation error - show fallback with error info
                        error_str = str(gen_error)
                        st.warning(f"⚠️ AI generation issue: {error_str}")
                        
                        # Always provide a helpful answer
                        soh = daily.get('soh_pct', 100.0)
                        soc = state.get('soc', 0.5) * 100
                        answer = f"""Based on your current battery status:

- **State of Charge (SOC)**: {soc:.1f}%
- **State of Health (SOH)**: {soh:.1f}%

**General Charging Habits:**
- Avoid keeping battery at 100% for extended periods
- Try to keep charge between 20-80% for optimal health
- Avoid deep discharges below 20%
- Charge at moderate temperatures (20-25°C)
- Avoid fast charging when not necessary
- Use slow charging when possible to reduce stress"""
                        st.markdown(answer)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": answer
                        })
            except Exception as e:
                error_msg = f"Sorry, I encountered an error: {str(e)}"
                st.error(error_msg)
                import traceback
                st.code(traceback.format_exc())
                
                # Still provide a basic answer
                try:
                    soh = daily.get('soh_pct', 100.0)
                    soc = state.get('soc', 0.5) * 100
                    fallback = f"""Based on your current battery status:

- **State of Charge (SOC)**: {soc:.1f}%
- **State of Health (SOH)**: {soh:.1f}%

**General Charging Habits:**
- Keep charge between 20-80% for optimal health
- Avoid deep discharges and overcharging
- Charge at moderate temperatures"""
                    st.markdown(fallback)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": fallback
                    })
                except:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })

# Sidebar info
with st.sidebar:
    st.markdown("### 💡 Tips")
    st.markdown("""
    - Ask about battery health, charge level, or degradation
    - Questions are answered using AI analysis of your battery data
    - Example: "What is my battery health?" or "Should I charge my battery?"
    """)
    
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

