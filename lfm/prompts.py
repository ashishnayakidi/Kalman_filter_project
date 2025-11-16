"""Prompt templates for LFM Q&A and reports."""
import json
import re
from typing import Dict, Any, Literal


def classify_intent(question: str) -> Literal["greeting", "battery", "off_topic"]:
    """
    Classify user question intent.
    
    Args:
        question: User question
    
    Returns:
        Intent classification: "greeting", "battery", or "off_topic"
    """
    question_lower = question.lower().strip()
    
    # Greeting patterns
    greeting_patterns = [
        r'^(hi|hello|hey|greetings|good morning|good afternoon|good evening|howdy)',
        r'^(thanks|thank you|thx|ty)',
        r'^(how are you|how\'?s it going|what\'?s up|sup)',
        r'^(bye|goodbye|see you|farewell)',
        r'^(yes|no|ok|okay|sure|alright|yep|nope)$',
    ]
    
    # Check for greetings
    for pattern in greeting_patterns:
        if re.match(pattern, question_lower):
            return "greeting"
    
    # Battery-related keywords
    battery_keywords = [
        'battery', 'soh', 'soc', 'health', 'charge', 'charging', 'degradation',
        'degrade', 'capacity', 'voltage', 'current', 'temperature', 'temp',
        'life', 'lifetime', 'remaining', 'useful', 'rul', 'range', 'mileage',
        'efficiency', 'stress', 'thermal', 'dcir', 'residual', 'prediction',
        'should i', 'when', 'how long', 'buy', 'replace', 'warranty', 'warrant',
        'recommend', 'advice', 'suggestion', 'optimal', 'best', 'worst',
        'problem', 'issue', 'fault', 'error', 'warning', 'alert'
    ]
    
    # Check for battery-related content
    for keyword in battery_keywords:
        if keyword in question_lower:
            return "battery"
    
    # If question is very short and doesn't match anything, likely greeting
    if len(question_lower.split()) <= 2 and not any(char.isdigit() for char in question_lower):
        return "greeting"
    
    # Default to battery if unclear (conservative approach)
    # But if it's clearly off-topic, mark it
    off_topic_keywords = [
        'weather', 'sports', 'politics', 'recipe', 'cooking', 'movie', 'music',
        'game', 'sport', 'news', 'stock', 'crypto', 'bitcoin', 'election'
    ]
    
    for keyword in off_topic_keywords:
        if keyword in question_lower:
            return "off_topic"
    
    # Default: assume battery-related (since this is a battery health chat)
    return "battery"


def build_greeting_prompt(question: str) -> str:
    """
    Build prompt for greetings and casual conversation.
    
    Args:
        question: User question
    
    Returns:
        Formatted prompt for greetings
    """
    question_lower = question.lower().strip()
    
    # Very simple, direct prompts based on greeting type
    if question_lower.startswith(('hi', 'hello', 'hey')):
        prompt = """User said: "hi" or "hello"

Respond with a simple greeting like "Hello! How can I help you with battery health questions today?"

Keep it to ONE sentence only. Just greet them back. Do not include examples or explanations."""
    elif 'thank' in question_lower or 'thanks' in question_lower:
        prompt = """User said: "thanks" or "thank you"

Respond with: "You're welcome! Feel free to ask if you need help with battery health questions."

Keep it to ONE sentence only."""
    elif 'how are you' in question_lower or 'how\'s it going' in question_lower:
        prompt = """User asked: "how are you"

Respond with: "I'm doing well, thanks! I'm here to help with battery health questions. What would you like to know?"

Keep it to ONE sentence only."""
    else:
        prompt = f"""User said: "{question}"

Respond with a brief, friendly greeting (ONE sentence). Mention you're here to help with battery health questions.

Keep it short and natural. Only ONE sentence."""
    
    return prompt


def build_off_topic_prompt(question: str) -> str:
    """
    Build prompt for off-topic questions.
    
    Args:
        question: User question
    
    Returns:
        Formatted prompt for off-topic questions
    """
    prompt = f"""You are a battery health assistant. The user has asked a question that doesn't seem related to battery health.

User question: {question}

Politely redirect them back to battery health topics. Be friendly and helpful. Suggest they can ask about battery health, charging habits, degradation, or battery life.

Keep it brief (2-3 sentences).
"""
    return prompt


def build_battery_prompt(question: str, daily_summary: Dict[str, Any], minute_rollup: Dict[str, Any]) -> str:
    """
    Build prompt for battery-related questions with full context.
    
    Args:
        question: User question
        daily_summary: Daily summary dict
        minute_rollup: Minute rollup dict
    
    Returns:
        Formatted prompt with battery data
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


def build_qna_prompt(question: str, daily_summary: Dict[str, Any], minute_rollup: Dict[str, Any]) -> str:
    """
    Build Q&A prompt with intent-aware routing.
    
    This is a convenience function that classifies intent and routes to appropriate prompt builder.
    For direct control, use build_greeting_prompt, build_battery_prompt, or build_off_topic_prompt.
    
    Args:
        question: User question
        daily_summary: Daily summary dict
        minute_rollup: Minute rollup dict
    
    Returns:
        Formatted prompt based on intent
    """
    intent = classify_intent(question)
    
    if intent == "greeting":
        return build_greeting_prompt(question)
    elif intent == "off_topic":
        return build_off_topic_prompt(question)
    else:  # battery
        return build_battery_prompt(question, daily_summary, minute_rollup)


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
- Charging Efficiency: {daily_summary.get('predictions', {}).get('charging_efficiency_pct', 0):.1f}%
- Energy Consumption: {daily_summary.get('predictions', {}).get('energy_consumption_wh_per_km', 0):.0f} Wh/km
- Predicted Range: {daily_summary.get('predictions', {}).get('predicted_range_km', 0):.0f} km
- Range Drop Since New: {daily_summary.get('predictions', {}).get('range_drop_km', 0):.0f} km
- Warranty Health Score: {daily_summary.get('predictions', {}).get('warranty_health_score', 100):.0f}/100
- Driving Style: {daily_summary.get('predictions', {}).get('driving_style', {}).get('style', 'unknown')}
- Thermal Stress Index: {daily_summary.get('predictions', {}).get('thermal_stress_index', 0):.1f} weighted hours

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

