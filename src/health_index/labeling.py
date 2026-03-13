"""
Labeling Module

Generates labels for supervised learning or anomaly detection based on percentile analysis.
"""

from typing import List, Tuple
import pandas as pd
import numpy as np

from .config import (
    UNIT_COL,
    LABELING_PERCENTILES,
    ANOMALY_THRESHOLD_RATIO,
)


def compute_percentile_thresholds(df: pd.DataFrame, signal_cols: List[str], 
                                   percentiles: Tuple[float, float] = LABELING_PERCENTILES) -> dict:
    """
    Compute percentile thresholds for each signal.
    
    Args:
        df: Input DataFrame
        signal_cols: List of signal column names
        percentiles: Tuple of (lower, upper) percentile values (e.g., (0.05, 0.95))
    
    Returns:
        Dictionary mapping signal names to {lower: value, upper: value}
    """
    thresholds = {}
    
    for col in signal_cols:
        if col in df.columns:
            lower_val = df[col].quantile(percentiles[0])
            upper_val = df[col].quantile(percentiles[1])
            thresholds[col] = {
                'lower': lower_val,
                'upper': upper_val,
            }
    
    return thresholds


def flag_out_of_range(df: pd.DataFrame, signal_cols: List[str],
                       exclude_patterns: List[str] = None) -> pd.DataFrame:
    """
    Flag data points outside the P5-P95 range for each signal.
    
    Args:
        df: Input DataFrame
        signal_cols: List of signal columns
        exclude_patterns: List of patterns to exclude from analysis (e.g., ['GPS', 'Spd'])
    
    Returns:
        DataFrame with added out-of-range flag columns
    """
    if exclude_patterns is None:
        exclude_patterns = ['GPS', 'Spd']
    
    df_out = df.copy()
    
    # Filter signals
    filtered_cols = [
        col for col in signal_cols
        if not any(pattern in col for pattern in exclude_patterns)
    ]
    
    # Compute thresholds
    thresholds = compute_percentile_thresholds(df_out, filtered_cols)
    
    # Create flag columns
    out_cols = []
    for col, bounds in thresholds.items():
        flag_col = f'{col}_out_range'
        df_out[flag_col] = ~df_out[col].between(bounds['lower'], bounds['upper'])
        out_cols.append(flag_col)
    
    return df_out, out_cols


def label_cycles_by_anomaly_ratio(df: pd.DataFrame, out_cols: List[str],
                                    threshold_ratio: float = ANOMALY_THRESHOLD_RATIO) -> pd.DataFrame:
    """
    Label cycles as Normal or Anomalous based on out-of-range ratio.
    
    Args:
        df: DataFrame with out-of-range flags and cycle_id
        out_cols: List of out-of-range flag column names
        threshold_ratio: Ratio threshold for anomaly (e.g., 1.2 means 120% of baseline)
    
    Returns:
        DataFrame with 'Label' column added
    """
    # Aggregate by cycle
    cycle_summary = df.groupby([UNIT_COL, 'cycle_id'])[out_cols].sum()
    cycle_total = df.groupby([UNIT_COL, 'cycle_id']).size().rename('total_rows')
    
    cycle_summary['total_out_range'] = cycle_summary[out_cols].sum(axis=1)
    cycle_summary = cycle_summary.merge(cycle_total, left_index=True, right_index=True)
    cycle_summary['total_ratio'] = cycle_summary['total_out_range'] / cycle_summary['total_rows']
    
    # Apply threshold
    cycle_summary['Label'] = np.where(
        cycle_summary['total_ratio'] < threshold_ratio,
        'Normal',
        'Anomalous'
    )
    
    # Merge back to original DataFrame
    df_labeled = df.merge(
        cycle_summary['Label'],
        left_on=[UNIT_COL, 'cycle_id'],
        right_index=True
    )
    
    # Drop flag columns to save memory
    df_labeled.drop(columns=out_cols, inplace=True, errors='ignore')
    
    return df_labeled


def create_labels(df: pd.DataFrame, signal_cols: List[str]) -> pd.DataFrame:
    """
    Complete labeling pipeline.
    
    Args:
        df: Input DataFrame with cycles
        signal_cols: List of signal columns
    
    Returns:
        Labeled DataFrame
    """
    print("Computing percentile thresholds and flagging anomalies...")
    df_flagged, out_cols = flag_out_of_range(df, signal_cols)
    
    print("Labeling cycles...")
    df_labeled = label_cycles_by_anomaly_ratio(df_flagged, out_cols)
    
    label_counts = df_labeled['Label'].value_counts()
    print(f"Label distribution:\n{label_counts}")
    
    return df_labeled
