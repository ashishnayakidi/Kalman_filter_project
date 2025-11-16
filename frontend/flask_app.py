"""Flask frontend application for battery monitoring dashboard."""
from flask import Flask, render_template, request, jsonify, session
from pathlib import Path
import sys
from datetime import datetime

# Add parent directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import shared utilities
from frontend.utils import (
    initialize_app, get_ekf, get_scorer_instance, get_lfm,
    fetch_and_process_data, get_fetch_status
)
from agent.scoring import daily_summary, minute_rollup
from lfm.prompts import build_qna_prompt, build_weekly_report_prompt

app = Flask(__name__)
app.secret_key = 'battery-agent-secret-key-change-in-production'
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# Initialize app on startup (includes automatic hourly fetching)
initialize_app()


@app.route('/')
def index():
    """Landing page."""
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    """Dashboard page."""
    return render_template('dashboard.html')


@app.route('/chat')
def chat():
    """Chat page."""
    return render_template('chat.html')


@app.route('/reports')
def reports():
    """Reports page."""
    return render_template('reports.html')


@app.route('/api/state')
def api_state():
    """Get current EKF state."""
    try:
        ekf = get_ekf()
        state = ekf.get_state()
        return jsonify(state)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/daily')
def api_daily():
    """Get daily summary."""
    try:
        scorer = get_scorer_instance()
        summary = scorer.daily_summary()
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/minute')
def api_minute():
    """Get minute rollup."""
    try:
        rollup = minute_rollup()
        return jsonify(rollup)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/history')
def api_history():
    """Get EKF history for charts."""
    try:
        ekf = get_ekf()
        # Return last 1000 points
        history = ekf.history[-1000:] if len(ekf.history) > 0 else []
        return jsonify(history)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ask', methods=['POST'])
def api_ask():
    """Handle chat question."""
    try:
        data = request.json
        question = data.get('question', '')
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        # Get current data
        scorer = get_scorer_instance()
        daily = scorer.daily_summary()
        minute = minute_rollup()
        ekf = get_ekf()
        state = ekf.get_state()
        
        # Try to use LFM
        lfm = get_lfm()
        if lfm is None:
            # Fallback: Basic answer
            soh = daily.get('soh_pct', 100.0)
            soc = state.get('soc', 0.5) * 100
            answer = f"""Based on your current battery status:

- **State of Charge (SOC)**: {soc:.1f}%
- **State of Health (SOH)**: {soh:.1f}%

"""
            if 'health' in question.lower() or 'soh' in question.lower():
                if soh >= 90:
                    answer += "Your battery health is excellent. Continue normal usage patterns."
                elif soh >= 80:
                    answer += "Your battery health is good. Monitor for any degradation trends."
                else:
                    answer += "Your battery health is declining. Consider reducing fast charging and high temperature exposure."
            elif 'charge' in question.lower() or 'charging' in question.lower() or 'soc' in question.lower():
                answer += f"Current charge level is {soc:.1f}%. "
                if soc < 20:
                    answer += "Consider charging soon to avoid deep discharge."
                elif soc > 80:
                    answer += "Battery is well charged."
                else:
                    answer += "Battery charge level is moderate."
                if 'habit' in question.lower() or 'suggest' in question.lower():
                    answer += "\n\n**General Charging Habits:**\n- Avoid keeping battery at 100% for extended periods\n- Try to keep charge between 20-80% for optimal health\n- Avoid deep discharges below 20%\n- Charge at moderate temperatures (20-25°C)\n- Avoid fast charging when not necessary"
            else:
                answer += "For detailed AI-powered analysis, please ensure the LFM2-350M model is available."
            
            return jsonify({'answer': answer, 'source': 'fallback'})
        else:
            # Use LFM
            prompt_text = build_qna_prompt(question, daily, minute)
            answer = lfm.generate(prompt_text, max_tokens=2048)
            
            if not answer or len(answer.strip()) == 0:
                # Empty response - use fallback
                soh = daily.get('soh_pct', 100.0)
                soc = state.get('soc', 0.5) * 100
                answer = f"""Based on your current battery status:

- **State of Charge (SOC)**: {soc:.1f}%
- **State of Health (SOH)**: {soh:.1f}%

The AI model returned an empty response. Here's a basic answer based on your battery data."""
                if 'charge' in question.lower() or 'charging' in question.lower():
                    answer += "\n\n**General Charging Habits:**\n- Avoid keeping battery at 100% for extended periods\n- Try to keep charge between 20-80% for optimal health\n- Avoid deep discharges below 20%\n- Charge at moderate temperatures (20-25°C)\n- Avoid fast charging when not necessary"
            
            return jsonify({'answer': answer, 'source': 'ai'})
            
    except Exception as e:
        import traceback
        error_msg = f"Error generating response: {str(e)}"
        return jsonify({'error': error_msg, 'traceback': traceback.format_exc()}), 500


@app.route('/api/weekly_report', methods=['POST'])
def api_weekly_report():
    """Generate weekly report."""
    try:
        scorer = get_scorer_instance()
        daily = scorer.daily_summary()
        
        # Extract metrics
        soh = daily.get('soh_pct', 100.0)
        dsoh = daily.get('dsoh_pct_per_week', 0.0)
        charge_count = daily.get('charge_count_week', 0)
        predictions = daily.get('predictions', {})
        rul_days = predictions.get('rul_days')
        rul_confidence = predictions.get('rul_confidence', 0.0)
        
        # Format RUL
        if rul_days is not None:
            if rul_days > 365:
                rul_text = f"approximately {int(rul_days/365)} years"
            elif rul_days > 30:
                rul_text = f"approximately {int(rul_days/30)} months"
            else:
                rul_text = f"approximately {int(rul_days)} days"
        else:
            rul_text = "unable to predict (insufficient data)"
        
        # Try to use LFM
        lfm = get_lfm()
        if lfm is None:
            # Fallback: Basic summary in layman terms
            report = f"""# Weekly Battery Health Report

## Executive Summary
Your battery is currently at **{soh:.1f}% health** (100% means brand new, 80% means it needs replacement). This week, your battery health {'decreased' if dsoh < 0 else 'increased' if dsoh > 0 else 'stayed the same'} by **{abs(dsoh):.2f}%**.

## Charging Activity
You charged your battery **{charge_count} times** this week. {'This is a normal charging frequency.' if 3 <= charge_count <= 10 else 'You may want to charge less frequently to preserve battery life.' if charge_count > 10 else 'Consider charging more regularly to maintain optimal battery health.'}

## Battery Degradation
{'Your battery is degrading at a rate of ' + f'{abs(dsoh*4.33):.2f}% per month.' if dsoh < 0 else 'Your battery health is stable or improving.'} {'This is a normal degradation rate.' if abs(dsoh) < 0.5 else 'This degradation rate is faster than normal. Consider reducing fast charging and high temperature exposure.'}

## Remaining Useful Life
Based on current trends, your battery is expected to last **{rul_text}** ({rul_confidence*100:.0f}% confidence). This estimate assumes you continue your current usage patterns.

## Recommendations
1. **Monitor charging frequency**: Try to keep charging between 3-7 times per week for optimal battery health.
2. **Avoid fast charging when possible**: Use slower charging methods to reduce battery stress.
3. **Keep battery cool**: Avoid exposing your battery to high temperatures.
4. **Don't overcharge**: Try to keep battery charge between 20-80% when possible.
"""
            return jsonify({'report': report, 'source': 'fallback'})
        else:
            # Use LFM
            prompt_text = build_weekly_report_prompt(daily)
            report = lfm.generate(prompt_text, max_tokens=1024)
            
            if not report or len(report.strip()) == 0:
                # Fallback
                report = f"""# Weekly Battery Health Report

## Summary
- **SOH**: {daily.get('soh_pct', 100.0):.1f}%
- **SOH Change Rate**: {daily.get('dsoh_pct_per_week', 0.0):.2f}% per week

## Recommendations
1. Monitor SOH trends weekly
2. Avoid excessive fast charging
3. Maintain moderate temperature ranges
"""
            
            return jsonify({'report': report, 'source': 'ai'})
            
    except Exception as e:
        import traceback
        error_msg = f"Error generating report: {str(e)}"
        return jsonify({'error': error_msg, 'traceback': traceback.format_exc()}), 500


@app.route('/api/fetch', methods=['POST'])
def api_fetch():
    """Manually trigger data fetch."""
    import threading
    
    def fetch_in_background():
        """Run fetch in background thread."""
        try:
            fetch_and_process_data(force=True)
        except Exception as e:
            print(f"Background fetch error: {e}")
    
    try:
        # Start fetch in background thread to avoid blocking
        thread = threading.Thread(target=fetch_in_background, daemon=True)
        thread.start()
        
        # Return immediately with status
        status = get_fetch_status()
        return jsonify({
            'success': True, 
            'message': 'Fetch started in background. Check terminal for progress.',
            'status': status
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/fetch_status')
def api_fetch_status():
    """Get fetch status."""
    try:
        status = get_fetch_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

