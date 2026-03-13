"""
Preprocessing Module

Handles outlier detection and removal.
"""

from typing import Dict, Tuple
import pandas as pd

from .config import OUTLIER_MARGINS


def clean_outliers(df: pd.DataFrame, margins: Dict[str, Tuple[float, float]] = None) -> pd.DataFrame:
    """
    Replace outliers with NaN based on predefined margins.
    
    Args:
        df: Input DataFrame
        margins: Dictionary mapping column names to (lower, upper) bounds.
                 If None, uses default OUTLIER_MARGINS from config.
    
    Returns:
        DataFrame with outliers replaced by NaN
    """
    if margins is None:
        margins = OUTLIER_MARGINS
    
    df_clean = df.copy()
    
    for col, (lower, upper) in margins.items():
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].where(
                (df_clean[col] >= lower) & (df_clean[col] <= upper),
                other=pd.NA
            )
    
    return df_clean


def drop_rows_with_missing_signals(df: pd.DataFrame, num_cols: list, threshold: float = 0.5) -> pd.DataFrame:
    """
    Drop rows where more than threshold fraction of signals are missing.
    
    Args:
        df: Input DataFrame
        num_cols: List of numeric column names to check
        threshold: Minimum fraction of non-null values required (0 to 1)
    
    Returns:
        DataFrame with rows dropped
    """
    df_out = df.copy()
    existing_num_cols = [col for col in num_cols if col in df_out.columns]
    
    if not existing_num_cols:
        return df_out
    
    min_count = int(len(existing_num_cols) * threshold)
    df_out.dropna(subset=existing_num_cols, thresh=min_count, inplace=True)
    
    return df_out


def fill_categorical_missing(df: pd.DataFrame, cat_cols: list, fill_values: Dict[str, str] = None) -> pd.DataFrame:
    """
    Fill missing categorical values with defaults.
    
    Args:
        df: Input DataFrame
        cat_cols: List of categorical column names
        fill_values: Dictionary mapping column names to fill values.
                     Defaults to sensible defaults if None.
    
    Returns:
        DataFrame with categorical NaNs filled
    """
    if fill_values is None:
        fill_values = {
            'EstadoMaquina': 'ND',
            'EstadoCarga': 'Sin Carga'
        }
    
    df_out = df.copy()
    
    for col in cat_cols:
        if col in df_out.columns and col in fill_values:
            df_out[col].fillna(fill_values[col], inplace=True)
    
    return df_out
