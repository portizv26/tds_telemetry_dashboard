"""
Health Index Module

Computes health index from reconstruction errors to assess equipment condition.
"""

import numpy as np
import pandas as pd
from typing import Optional

from .config import (
    UNIT_COL,
    TIME_COL,
    HEALTH_INDEX_ALPHA,
    HEALTH_INDEX_AGG_METHOD,
    HEALTH_INDEX_EPS,
)


def compute_health_index(
    reconstruction_errors: np.ndarray,
    alpha: float = HEALTH_INDEX_ALPHA,
    eps: float = HEALTH_INDEX_EPS,
) -> np.ndarray:
    """
    Compute health index from reconstruction errors.
    
    Health Index is computed as:
        HI = 100 * exp(-alpha * normalized_error)
    
    Where:
        - 100 = perfect health
        - Lower values = degraded health
        - normalized_error = (error - min) / (max - min + eps)
    
    Args:
        reconstruction_errors: Array of reconstruction errors
        alpha: Sensitivity parameter (higher = more sensitive to errors)
        eps: Small constant to avoid division by zero
    
    Returns:
        Health index values between 0 and 100
    """
    # Normalize errors to [0, 1]
    err_min = reconstruction_errors.min()
    err_max = reconstruction_errors.max()
    
    normalized_errors = (reconstruction_errors - err_min) / (err_max - err_min + eps)
    
    # Compute health index
    health_index = 100 * np.exp(-alpha * normalized_errors)
    
    return health_index


def aggregate_health_index_per_unit(
    df: pd.DataFrame,
    method: str = HEALTH_INDEX_AGG_METHOD,
) -> pd.DataFrame:
    """
    Aggregate health index per unit over time.
    
    Args:
        df: DataFrame with health_index and Unit columns
        method: Aggregation method ('mean', 'median', 'min')
    
    Returns:
        DataFrame with aggregated health index per unit
    """
    if method == 'mean':
        agg_func = 'mean'
    elif method == 'median':
        agg_func = 'median'
    elif method == 'min':
        agg_func = 'min'
    else:
        raise ValueError(f"Unknown aggregation method: {method}")
    
    result = df.groupby(UNIT_COL).agg({
        'health_index': agg_func,
        'reconstruction_error': ['mean', 'std', 'max'],
        'start_time': 'min',
        'end_time': 'max',
    }).reset_index()
    
    # Flatten column names
    result.columns = ['_'.join(col).strip('_') for col in result.columns.values]
    
    return result


def categorize_health_status(health_index: np.ndarray) -> np.ndarray:
    """
    Categorize health index into discrete health statuses.
    
    Categories:
        - Excellent: HI >= 90
        - Good: 70 <= HI < 90
        - Fair: 50 <= HI < 70
        - Poor: 30 <= HI < 50
        - Critical: HI < 30
    
    Args:
        health_index: Array of health index values
    
    Returns:
        Array of health status categories
    """
    status = np.empty(len(health_index), dtype=object)
    
    status[health_index >= 90] = 'Excellent'
    status[(health_index >= 70) & (health_index < 90)] = 'Good'
    status[(health_index >= 50) & (health_index < 70)] = 'Fair'
    status[(health_index >= 30) & (health_index < 50)] = 'Poor'
    status[health_index < 30] = 'Critical'
    
    return status


def compute_health_index_from_inference(
    inference_df: pd.DataFrame,
    alpha: float = HEALTH_INDEX_ALPHA,
) -> pd.DataFrame:
    """
    Complete health index computation from inference results.
    
    Args:
        inference_df: DataFrame from inference with reconstruction_error column
        alpha: Sensitivity parameter
    
    Returns:
        DataFrame with health_index and health_status columns added
    """
    df = inference_df.copy()
    
    # Compute health index
    df['health_index'] = compute_health_index(
        df['reconstruction_error'].values,
        alpha=alpha,
    )
    
    # Categorize health status
    df['health_status'] = categorize_health_status(df['health_index'].values)
    
    print(f"\nHealth Index Statistics:")
    print(f"  Mean: {df['health_index'].mean():.2f}")
    print(f"  Median: {df['health_index'].median():.2f}")
    print(f"  Std: {df['health_index'].std():.2f}")
    print(f"  Min: {df['health_index'].min():.2f}")
    print(f"  Max: {df['health_index'].max():.2f}")
    
    print(f"\nHealth Status Distribution:")
    print(df['health_status'].value_counts().sort_index())
    
    return df


def compute_trend(df: pd.DataFrame, time_col: str = 'end_time', 
                  value_col: str = 'health_index') -> pd.DataFrame:
    """
    Compute trend statistics for health index over time.
    
    Args:
        df: DataFrame with time and health index
        time_col: Name of time column
        value_col: Name of value column
    
    Returns:
        DataFrame with trend statistics per unit
    """
    results = []
    
    for unit in df[UNIT_COL].unique():
        unit_data = df[df[UNIT_COL] == unit].sort_values(time_col)
        
        if len(unit_data) < 2:
            continue
        
        # Linear trend (slope)
        x = np.arange(len(unit_data))
        y = unit_data[value_col].values
        
        slope, intercept = np.polyfit(x, y, 1)
        
        results.append({
            UNIT_COL: unit,
            'trend_slope': slope,
            'trend_direction': 'improving' if slope > 0 else 'degrading',
            'first_hi': y[0],
            'last_hi': y[-1],
            'hi_change': y[-1] - y[0],
            'n_observations': len(unit_data),
        })
    
    return pd.DataFrame(results)
