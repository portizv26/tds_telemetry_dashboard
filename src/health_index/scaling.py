"""
Scaling Module

Handles per-unit scaling for numeric features and encoding for categorical features.
"""

from typing import List, Dict
import pandas as pd
import numpy as np
from sklearn.preprocessing import RobustScaler, OneHotEncoder
import joblib

from .config import UNIT_COL, CAT_COLS


def fit_scalers_per_unit(df: pd.DataFrame, num_cols: List[str]) -> Dict[str, RobustScaler]:
    """
    Fit a separate RobustScaler for each unit.
    
    This is critical for handling equipment-specific baseline behavior.
    
    Args:
        df: Training DataFrame
        num_cols: List of numeric columns to scale
    
    Returns:
        Dictionary mapping unit names to fitted RobustScaler objects
    """
    scalers = {}
    
    for unit in df[UNIT_COL].unique():
        unit_mask = df[UNIT_COL] == unit
        unit_data = df.loc[unit_mask, num_cols]
        
        # Fit RobustScaler only on non-null data
        scaler = RobustScaler()
        scaler.fit(unit_data.dropna())
        scalers[unit] = scaler
    
    print(f"Fitted {len(scalers)} unit-specific scalers")
    return scalers


def apply_scalers_per_unit(df: pd.DataFrame, num_cols: List[str], 
                            scalers: Dict[str, RobustScaler]) -> pd.DataFrame:
    """
    Apply per-unit scaling to numeric features.
    
    Args:
        df: Input DataFrame
        num_cols: List of numeric columns to scale
        scalers: Dictionary of fitted scalers per unit
    
    Returns:
        DataFrame with scaled numeric columns
    """
    df_scaled = df.copy()
    
    for unit, scaler in scalers.items():
        unit_mask = df_scaled[UNIT_COL] == unit
        if unit_mask.sum() > 0:
            df_scaled.loc[unit_mask, num_cols] = scaler.transform(
                df_scaled.loc[unit_mask, num_cols].fillna(0)
            )
    
    return df_scaled


def fit_categorical_encoder(df: pd.DataFrame, cat_cols: List[str] = None) -> OneHotEncoder:
    """
    Fit OneHotEncoder for categorical features.
    
    Args:
        df: Training DataFrame
        cat_cols: List of categorical columns (defaults to CAT_COLS from config)
    
    Returns:
        Fitted OneHotEncoder
    """
    if cat_cols is None:
        cat_cols = CAT_COLS
    
    existing_cat_cols = [col for col in cat_cols if col in df.columns]
    
    if not existing_cat_cols:
        return None
    
    encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
    encoder.fit(df[existing_cat_cols])
    
    return encoder


def apply_categorical_encoder(df: pd.DataFrame, encoder: OneHotEncoder, 
                              cat_cols: List[str] = None) -> pd.DataFrame:
    """
    Apply OneHotEncoder to categorical features.
    
    Args:
        df: Input DataFrame
        encoder: Fitted OneHotEncoder
        cat_cols: List of categorical columns (defaults to CAT_COLS from config)
    
    Returns:
        DataFrame with one-hot encoded categorical columns
    """
    if cat_cols is None:
        cat_cols = CAT_COLS
    
    if encoder is None:
        return df
    
    existing_cat_cols = [col for col in cat_cols if col in df.columns]
    
    if not existing_cat_cols:
        return df
    
    df_out = df.copy()
    
    # Transform
    encoded = encoder.transform(df_out[existing_cat_cols])
    encoded_df = pd.DataFrame(
        encoded,
        columns=encoder.get_feature_names_out(existing_cat_cols),
        index=df_out.index
    )
    
    # Drop original categorical columns and add encoded
    df_out.drop(columns=existing_cat_cols, inplace=True)
    df_out = pd.concat([df_out, encoded_df], axis=1)
    
    return df_out


def save_scalers(scalers: Dict[str, RobustScaler], path: str):
    """Save unit-specific scalers to disk."""
    joblib.dump(scalers, path)
    print(f"Saved scalers to: {path}")


def load_scalers(path: str) -> Dict[str, RobustScaler]:
    """Load unit-specific scalers from disk."""
    return joblib.load(path)


def save_encoder(encoder: OneHotEncoder, path: str):
    """Save categorical encoder to disk."""
    joblib.dump(encoder, path)
    print(f"Saved encoder to: {path}")


def load_encoder(path: str) -> OneHotEncoder:
    """Load categorical encoder from disk."""
    return joblib.load(path)
