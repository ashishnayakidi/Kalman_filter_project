"""Prompt templates for LFM Q&A and reports."""
import json
from typing import Dict, Any


def build_qna_prompt(question: str, daily_summary: Dict[str, Any], minute_rollup: Dict[str, Any]) -> str:
    """
    Build Q&A prompt.
    
    Args:
        question: User question
        daily_summary: Daily summary dict
        minute_rollup: Minute rollup dict
    
    Returns:
        Formatted prompt
    """
    prompt = f"""You are a battery health expert. Answer the following question based on the battery monitoring data.

Question: {question}

Current Battery Status:
- SOH: {daily_summary.get('soh_pct', 100.0):.1f}%
- SOH Change Rate: {daily_summary.get('dsoh_pct_per_week', 0.0):.2f}% per week
- Current SOC: {minute_rollup.get('soc_mean', 0.5):.1%}
- Voltage Residual: {minute_rollup.get('residual_mean_mv', 0.0):.2f} mV
- Temperature: {minute_rollup.get('temp_mean_C', 25.0):.1f}°C

DCIR Changes:
{json.dumps(daily_summary.get('dcir_changes', {}), indent=2)}

Stress Metrics:
- Fast Charge Events: {daily_summary.get('stress', {}).get('fast_charge_count', 0)}
- Hours at High Temp: {daily_summary.get('stress', {}).get('hours_at_high_temp', 0.0):.1f}
- Hours at High SOC: {daily_summary.get('stress', {}).get('hours_at_high_soc', 0.0):.1f}

Drift:
- Residual Mean: {daily_summary.get('drift', {}).get('residual_mean_mv', 0.0):.2f} mV
- Residual Std: {daily_summary.get('drift', {}).get('residual_std_mv', 0.0):.2f} mV

Provide a concise explanation and 3 actionable recommendations.
"""
    return prompt


def build_weekly_report_prompt(daily_summary: Dict[str, Any]) -> str:
    """
    Build weekly report prompt with layman-friendly instructions.
    
    Args:
        daily_summary: Daily summary dict
    
    Returns:
        Formatted prompt
    """
    charge_count = daily_summary.get('charge_count_week', 0)
    soh = daily_summary.get('soh_pct', 100.0)
    dsoh = daily_summary.get('dsoh_pct_per_week', 0.0)
    predictions = daily_summary.get('predictions', {})
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
    
    prompt = f"""You are a battery health expert writing a weekly report for a non-technical user. Write in simple, easy-to-understand language. Avoid technical jargon. Use analogies when helpful.

Battery Data:
- Current Battery Health: {soh:.1f}% (100% = brand new, 80% = needs replacement)
- Health Change This Week: {dsoh:.2f}% {'(degrading)' if dsoh < 0 else '(improving)' if dsoh > 0 else '(stable)'}
- Number of Times Charged This Week: {charge_count}
- Remaining Useful Life: {rul_text} (confidence: {rul_confidence*100:.0f}%)
- Degradation Rate: {abs(dsoh*4.33):.2f}% per month

Full Data:
{json.dumps(daily_summary, indent=2)}

Write a weekly battery health report with these sections:

1. **Executive Summary** (2-3 sentences)
   - Current battery health in simple terms
   - Whether it's getting better or worse
   - Overall assessment (excellent/good/fair/poor)

2. **Charging Activity**
   - How many times the battery was charged this week
   - Whether this is normal, too frequent, or too infrequent
   - Simple explanation of what this means

3. **Battery Degradation**
   - Did the battery degrade this week? By how much?
   - Is the degradation rate normal, fast, or slow?
   - What this means in practical terms

4. **Remaining Useful Life**
   - How long the battery is expected to last
   - Confidence level of this prediction
   - What factors could change this estimate

5. **Recommendations** (3-5 actionable items)
   - Specific, simple actions the user can take
   - Prioritized by importance
   - Written in plain language

Use simple language throughout. Avoid technical terms like "DCIR", "CUSUM", "residual". Instead use terms like "battery health", "charging speed", "battery life", etc.
"""
    return prompt

