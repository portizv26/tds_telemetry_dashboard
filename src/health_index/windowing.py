"""
Windowing Module

Creates sliding windows/sequences for LSTM input.
"""

from typing import List, Tuple
import numpy as np
import pandas as pd
from tqdm.auto import tqdm

from .config import UNIT_COL, TIME_COL


def create_windows(df: pd.DataFrame, feature_cols: List[str], window_size: int,
                   stride: int = 1, exclude_flags: bool = True) -> Tuple[np.ndarray, pd.DataFrame]:
    """
    Create sliding windows for sequence modeling.
    
    Args:
        df: Input DataFrame
        feature_cols: List of feature columns to use
        window_size: Number of timesteps per window
        stride: Step size for sliding window
        exclude_flags: Whether to exclude rows with created_by_reindex or imputed_any flags
    
    Returns:
        Tuple of:
        - X: numpy array of shape (n_windows, window_size, n_features)
        - metadata: DataFrame with window metadata (unit, start_time, end_time, etc.)
    """
    df_work = df.copy()
    
    # Validate that all feature columns are numeric
    non_numeric_cols = [col for col in feature_cols if col in df_work.columns 
                        and not pd.api.types.is_numeric_dtype(df_work[col])]
    if non_numeric_cols:
        raise ValueError(f"Non-numeric columns found in feature_cols: {non_numeric_cols}")
    
    # Filter out synthetic/imputed data if requested
    if exclude_flags:
        if 'created_by_reindex' in df_work.columns:
            df_work = df_work[df_work['created_by_reindex'] == 0]
        if 'imputed_any' in df_work.columns:
            df_work = df_work[df_work['imputed_any'] == 0]
    
    windows = []
    metadata = []
    
    # Group by unit and cycle to maintain temporal continuity
    if 'cycle_id' in df_work.columns:
        group_cols = [UNIT_COL, 'cycle_id']
    else:
        group_cols = [UNIT_COL]
    
    grouped = df_work.groupby(group_cols, sort=False)
    
    for group_keys, group_df in tqdm(grouped, desc="Creating windows"):
        # Extract feature values and ensure numeric type
        try:
            values = group_df[feature_cols].values.astype(np.float32)
        except (ValueError, TypeError) as e:
            # Skip this group if conversion fails
            continue
        
        # Skip if not enough data
        if len(values) < window_size:
            continue
        
        # Create sliding windows
        for i in range(0, len(values) - window_size + 1, stride):
            window = values[i:i+window_size]
            
            # Skip if any NaN in window
            if np.isnan(window).any():
                continue
            
            windows.append(window)
            
            # Store metadata
            meta = {
                UNIT_COL: group_df[UNIT_COL].iloc[i],
                'start_time': group_df[TIME_COL].iloc[i],
                'end_time': group_df[TIME_COL].iloc[i+window_size-1],
            }
            
            if 'cycle_id' in group_df.columns:
                meta['cycle_id'] = group_df['cycle_id'].iloc[i]
            
            if 'Label' in group_df.columns:
                # Use majority label in window
                labels_in_window = group_df['Label'].iloc[i:i+window_size]
                meta['Label'] = labels_in_window.mode()[0] if len(labels_in_window) > 0 else None
            
            metadata.append(meta)
    
    if not windows:
        print("Warning: No valid windows created")
        return np.array([]).reshape(0, window_size, len(feature_cols)), pd.DataFrame()
    
    X = np.array(windows, dtype=np.float32)
    metadata_df = pd.DataFrame(metadata)
    
    print(f"Created {len(X):,} windows of shape {X.shape}")
    
    return X, metadata_df


def create_single_window_inference(df: pd.DataFrame, feature_cols: List[str], 
                                    window_size: int) -> Tuple[np.ndarray, pd.DataFrame]:
    """
    Create one window per unit from the most recent data.
    
    Used for real-time or single-point-in-time inference.
    
    Args:
        df: Input DataFrame
        feature_cols: List of feature columns
        window_size: Window size
    
    Returns:
        Tuple of (X, metadata) where X has shape (n_units, window_size, n_features)
    """
    windows = []
    metadata = []
    
    for unit in df[UNIT_COL].unique():
        unit_data = df[df[UNIT_COL] == unit]
        
        # Take last window_size timesteps
        if len(unit_data) < window_size:
            continue
        
        last_window = unit_data.iloc[-window_size:]
        
        # Extract and convert to numeric
        try:
            values = last_window[feature_cols].values.astype(np.float32)
        except (ValueError, TypeError):
            continue
        
        # Skip if NaN
        if np.isnan(values).any():
            continue
        
        windows.append(values)
        metadata.append({
            UNIT_COL: unit,
            'start_time': last_window[TIME_COL].iloc[0],
            'end_time': last_window[TIME_COL].iloc[-1],
        })
    
    if not windows:
        return np.array([]).reshape(0, window_size, len(feature_cols)), pd.DataFrame()
    
    X = np.array(windows, dtype=np.float32)
    metadata_df = pd.DataFrame(metadata)
    
    return X, metadata_df
