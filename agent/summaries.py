"""Summary generation utilities."""
from typing import Dict, List
from datetime import datetime


def format_minute_summary(rollup: Dict) -> str:
    """Format minute rollup as human-readable string."""
    return f"""Minute Summary:
  SOC: {rollup.get('soc_mean', 0.0):.1%} (±{rollup.get('soc_std', 0.0):.1%})
  Voltage Residual: {rollup.get('residual_mean_mv', 0.0):.2f} mV (±{rollup.get('residual_std_mv', 0.0):.2f} mV)
  Temperature: {rollup.get('temp_mean_C', 25.0):.1f}°C
  Ticks: {rollup.get('tick_count', 0)}
"""


def format_daily_summary(summary: Dict) -> str:
    """Format daily summary as human-readable string."""
    lines = [
        "Daily Summary:",
        f"  SOH: {summary.get('soh_pct', 100.0):.1f}%",
        f"  SOH Change: {summary.get('dsoh_pct_per_week', 0.0):.2f}% per week",
        "",
        "DCIR Changes:"
    ]
    
    dcir_changes = summary.get('dcir_changes', {})
    if dcir_changes:
        for key, val in dcir_changes.items():
            lines.append(f"  {key}: {val.get('rel_change_pct', 0.0):.1f}% "
                        f"({val.get('current_mohm', 0.0):.1f} mΩ)")
    else:
        lines.append("  No DCIR data available")
    
    stress = summary.get('stress', {})
    lines.extend([
        "",
        "Stress Metrics:",
        f"  Fast Charge Events: {stress.get('fast_charge_count', 0)}",
        f"  Hours at High Temp: {stress.get('hours_at_high_temp', 0.0):.1f}",
        f"  Hours at High SOC: {stress.get('hours_at_high_soc', 0.0):.1f}"
    ])
    
    drift = summary.get('drift', {})
    lines.extend([
        "",
        "Drift:",
        f"  Residual Mean: {drift.get('residual_mean_mv', 0.0):.2f} mV",
        f"  Residual Std: {drift.get('residual_std_mv', 0.0):.2f} mV"
    ])
    
    return "\n".join(lines)

