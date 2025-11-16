"""Open Circuit Voltage lookup and derivation."""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional


def ocv_lookup(soc: float, T_C: float, table: Optional[pd.DataFrame] = None) -> float:
    """
    Lookup OCV for given SOC and temperature.
    
    Args:
        soc: State of charge (0.0 to 1.0)
        T_C: Temperature in Celsius
        table: DataFrame with columns ['soc', 'temp_C', 'ocv_V'] or None for fallback
    
    Returns:
        OCV in Volts
    """
    if table is None:
        # Simple monotonic fallback: 3.0 + 1.2*soc
        return 3.0 + 1.2 * soc
    
    # Clip SOC to valid range
    soc = np.clip(soc, 0.0, 1.0)
    
    # Find nearest temperature bin
    if 'temp_C' in table.columns:
        temp_col = 'temp_C'
    elif 'temperature' in table.columns:
        temp_col = 'temperature'
    else:
        # Assume single temperature curve
        if 'soc' in table.columns and 'ocv_V' in table.columns:
            return np.interp(soc, table['soc'], table['ocv_V'])
        return 3.0 + 1.2 * soc
    
    # 2D interpolation: find nearest temp bins
    temps = table[temp_col].unique()
    if len(temps) == 1:
        # Single temperature
        temp_subset = table[table[temp_col] == temps[0]]
        if 'ocv_V' in temp_subset.columns:
            return np.interp(soc, temp_subset['soc'], temp_subset['ocv_V'])
    
    # Multi-temperature: find nearest temp
    nearest_temp = temps[np.argmin(np.abs(temps - T_C))]
    temp_subset = table[table[temp_col] == nearest_temp].sort_values('soc')
    
    if 'ocv_V' in temp_subset.columns:
        return np.interp(soc, temp_subset['soc'], temp_subset['ocv_V'])
    
    return 3.0 + 1.2 * soc


def derive_ocv_table(df: pd.DataFrame, 
                     current_col: str = 'current_A',
                     voltage_col: str = 'voltage_V',
                     temp_col: str = 'temp_C',
                     soc_col: Optional[str] = None,
                     rest_threshold: float = 0.05) -> pd.DataFrame:
    """
    Derive OCV table from processed dataframe using near-rest points.
    
    Args:
        df: Processed dataframe with voltage, current, temperature
        current_col: Column name for current
        voltage_col: Column name for voltage
        temp_col: Column name for temperature
        soc_col: Optional SOC column (if None, will estimate from capacity)
        rest_threshold: Current threshold for "rest" condition (A)
    
    Returns:
        DataFrame with columns ['soc', 'temp_C', 'ocv_V']
    """
    # Filter near-rest points
    rest_mask = np.abs(df[current_col]) < rest_threshold
    rest_df = df[rest_mask].copy()
    
    if len(rest_df) == 0:
        # Fallback: create synthetic table
        socs = np.linspace(0.0, 1.0, 21)
        temps = df[temp_col].unique() if temp_col in df.columns else [25.0]
        if len(temps) == 0:
            temps = [25.0]
        
        rows = []
        for temp in temps:
            for soc in socs:
                rows.append({'soc': soc, 'temp_C': temp, 'ocv_V': 3.0 + 1.2 * soc})
        return pd.DataFrame(rows)
    
    # Estimate SOC if not provided
    if soc_col is None or soc_col not in rest_df.columns:
        # Simple estimation: assume capacity-based SOC
        if 'capacity_Ah_cycle' in rest_df.columns:
            max_cap = rest_df['capacity_Ah_cycle'].max()
            rest_df['soc'] = rest_df['capacity_Ah_cycle'] / max_cap if max_cap > 0 else 0.5
        else:
            # Use time-based proxy
            rest_df['soc'] = np.linspace(1.0, 0.0, len(rest_df))
    
    # Group by SOC and temperature bins
    rest_df['soc_bin'] = (rest_df['soc'] * 20).round() / 20  # 5% bins
    if temp_col in rest_df.columns:
        rest_df['temp_bin'] = (rest_df[temp_col] / 5).round() * 5  # 5°C bins
    else:
        rest_df['temp_bin'] = 25.0
    
    # Average OCV per bin
    ocv_table = rest_df.groupby(['soc_bin', 'temp_bin'])[voltage_col].mean().reset_index()
    ocv_table.columns = ['soc', 'temp_C', 'ocv_V']
    ocv_table = ocv_table.sort_values(['temp_C', 'soc'])
    
    return ocv_table

