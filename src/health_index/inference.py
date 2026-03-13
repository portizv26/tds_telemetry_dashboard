"""
Inference Module

Handles single-window and multi-window inference for long horizons.
"""

import numpy as np
import pandas as pd
from typing import List, Tuple
from tensorflow import keras
from tqdm.auto import tqdm

from .config import UNIT_COL, TIME_COL
from .windowing import create_windows


def predict_single_window(model: keras.Model, X: np.ndarray) -> np.ndarray:
    """
    Generate predictions for a single batch of windows.
    
    Args:
        model: Trained autoencoder model
        X: Input data of shape (n_samples, window_size, n_features)
    
    Returns:
        Reconstructed data of same shape as input
    """
    return model.predict(X, verbose=0)


def compute_reconstruction_error(X_true: np.ndarray, X_pred: np.ndarray, 
                                  method: str = 'mse') -> np.ndarray:
    """
    Compute reconstruction error.
    
    Args:
        X_true: Original data
        X_pred: Reconstructed data
        method: Error metric ('mse', 'mae', 'rmse')
    
    Returns:
        Error per window (n_samples,)
    """
    if method == 'mse':
        # Mean squared error per window
        error = np.mean((X_true - X_pred) ** 2, axis=(1, 2))
    elif method == 'mae':
        # Mean absolute error per window
        error = np.mean(np.abs(X_true - X_pred), axis=(1, 2))
    elif method == 'rmse':
        # Root mean squared error per window
        error = np.sqrt(np.mean((X_true - X_pred) ** 2, axis=(1, 2)))
    else:
        raise ValueError(f"Unknown method: {method}")
    
    return error


def predict_over_horizon(
    df: pd.DataFrame,
    model: keras.Model,
    feature_cols: List[str],
    window_size: int,
    stride: int = 1,
    error_method: str = 'mse',
) -> pd.DataFrame:
    """
    Generate predictions over a long time horizon by sliding windows.
    
    This is the key function for multi-window inference that processes
    the full test set window by window.
    
    Args:
        df: Input DataFrame (e.g., full test set spanning weeks)
        model: Trained model
        feature_cols: List of feature columns
        window_size: Window size used during training
        stride: Stride for sliding window
        error_method: Reconstruction error metric
    
    Returns:
        DataFrame with reconstruction errors and metadata per window
    """
    print(f"\nGenerating predictions over horizon...")
    print(f"  Data shape: {df.shape}")
    print(f"  Window size: {window_size}")
    print(f"  Stride: {stride}")
    
    # Create windows
    X, metadata = create_windows(
        df=df,
        feature_cols=feature_cols,
        window_size=window_size,
        stride=stride,
        exclude_flags=False,  # Include all data for inference
    )
    
    if len(X) == 0:
        print("Warning: No valid windows created for inference")
        return pd.DataFrame()
    
    print(f"  Created {len(X):,} windows")
    
    # Predict in batches
    batch_size = 256
    reconstructions = []
    
    for i in tqdm(range(0, len(X), batch_size), desc="Predicting"):
        batch = X[i:i+batch_size]
        batch_pred = predict_single_window(model, batch)
        reconstructions.append(batch_pred)
    
    X_pred = np.concatenate(reconstructions, axis=0)
    
    # Compute reconstruction errors
    errors = compute_reconstruction_error(X, X_pred, method=error_method)
    
    # Add errors to metadata
    results = metadata.copy()
    results['reconstruction_error'] = errors
    
    # Compute per-signal errors (optional but useful for diagnosis)
    n_features = X.shape[2]
    for feat_idx, feat_name in enumerate(feature_cols):
        # Mean error for this feature across time dimension
        feat_error = np.mean((X[:, :, feat_idx] - X_pred[:, :, feat_idx]) ** 2, axis=1)
        results[f'{feat_name}_error'] = feat_error
    
    print(f"  Mean reconstruction error: {errors.mean():.6f}")
    print(f"  Std reconstruction error: {errors.std():.6f}")
    print(f"  Max reconstruction error: {errors.max():.6f}")
    
    return results


def predict_latest_window_per_unit(
    df: pd.DataFrame,
    model: keras.Model,
    feature_cols: List[str],
    window_size: int,
) -> pd.DataFrame:
    """
    Predict using the most recent window for each unit.
    
    Useful for real-time health monitoring.
    
    Args:
        df: Input DataFrame
        model: Trained model
        feature_cols: Feature columns
        window_size: Window size
    
    Returns:
        DataFrame with one prediction per unit
    """
    results = []
    
    for unit in df[UNIT_COL].unique():
        unit_data = df[df[UNIT_COL] == unit].sort_values(TIME_COL)
        
        # Take last window_size rows
        if len(unit_data) < window_size:
            continue
        
        last_window_df = unit_data.iloc[-window_size:]
        values = last_window_df[feature_cols].values
        
        # Skip if NaN
        if np.isnan(values).any():
            continue
        
        # Predict
        X = values.reshape(1, window_size, len(feature_cols)).astype(np.float32)
        X_pred = predict_single_window(model, X)
        
        # Error
        error = compute_reconstruction_error(X, X_pred, method='mse')[0]
        
        results.append({
            UNIT_COL: unit,
            'start_time': last_window_df[TIME_COL].iloc[0],
            'end_time': last_window_df[TIME_COL].iloc[-1],
            'reconstruction_error': error,
        })
    
    return pd.DataFrame(results)
