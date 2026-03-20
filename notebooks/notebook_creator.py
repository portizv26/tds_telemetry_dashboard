"""
Script to generate health_index_modular.ipynb

This script creates a notebook that orchestrates the Health Index workflow
using a service-oriented architecture driven by the full_mapping.json configuration.
"""

import os
import json
from pathlib import Path


def create_notebook():
    """Generate the health_index_modular.ipynb notebook."""
    
    notebook_cells = []
    
    # ==================== SECTION 1: Imports and Configuration ====================
    notebook_cells.append({
        "language": "markdown",
        "content": """# Health Index Modular Pipeline

This notebook orchestrates the Health Index workflow using a service-oriented architecture.

## Architecture Overview

The workflow is built on three main services:

1. **LSTMAutoencoderPreprocessor**: Handles data transformation, scaling, encoding, and window generation
2. **LSTMAutoencoderService**: Handles model creation, training, prediction, and persistence
3. **HealthIndexService**: Handles reconstruction error normalization, HI scoring, and consolidation

Execution is driven by `full_mapping.json` which defines truck models, components, and signals."""
    })
    
    notebook_cells.append({
        "language": "markdown",
        "content": """## 1. Imports and Configuration"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """# Standard library
import os
import json
import warnings
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Tuple

# Data processing
import numpy as np
import pandas as pd
from tqdm.auto import tqdm

# ML and deep learning
import tensorflow as tf
from tensorflow.keras import layers, Model
from sklearn.preprocessing import RobustScaler, OneHotEncoder
from numpy.lib.stride_tricks import sliding_window_view

# Hyperparameter optimization
import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler

# Experiment tracking
import mlflow
import mlflow.keras

# Utility
import joblib

# Suppress warnings
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

print(f"TensorFlow version: {tf.__version__}")
print(f"GPU Available: {tf.config.list_physical_devices('GPU')}")"""
    })
    
    # ==================== SECTION 2: GPU Configuration ====================
    notebook_cells.append({
        "language": "markdown",
        "content": """## 2. GPU Configuration"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """# Configure GPU memory growth
gpus = tf.config.list_physical_devices('GPU')
if gpus:
    try:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        print(f"✓ GPU memory growth enabled for {len(gpus)} GPU(s)")
        
        # Enable mixed precision for better performance
        from tensorflow.keras import mixed_precision
        policy = mixed_precision.Policy('mixed_float16')
        mixed_precision.set_global_policy(policy)
        print(f"✓ Mixed precision enabled: {policy.name}")
    except RuntimeError as e:
        print(f"GPU configuration error: {e}")
else:
    print("⚠ No GPU detected - training will use CPU")"""
    })
    
    # ==================== SECTION 3: Path Definitions ====================
    notebook_cells.append({
        "language": "markdown",
        "content": """## 3. Path Definitions"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """# Configuration
CLIENT = "cda"
UNIT_COL = "Unit"
TIME_COL = "Fecha"

# Base paths
BASE_DIR = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"

# Input paths
MAPPING_PATH = DATA_DIR / "telemetry" / "silver" / CLIENT / "full_mapping.json"
RAW_DATA_PATH = DATA_DIR / "telemetry" / "silver" / CLIENT / "Telemetry_Wide_With_States"

# Output paths
PROCESSED_DATA_PATH = DATA_DIR / "telemetry" / "silver" / CLIENT / "processed_data.parquet"
INFERENCES_PATH = DATA_DIR / "telemetry" / "golden" / CLIENT / "inferences.parquet"
HEALTH_INDEX_PATH = DATA_DIR / "telemetry" / "golden" / CLIENT / "health_index.parquet"

# Model paths
CLIENT_MODELS_DIR = MODELS_DIR / CLIENT

# Create directories
(DATA_DIR / "telemetry" / "silver" / CLIENT).mkdir(parents=True, exist_ok=True)
(DATA_DIR / "telemetry" / "golden" / CLIENT).mkdir(parents=True, exist_ok=True)
CLIENT_MODELS_DIR.mkdir(parents=True, exist_ok=True)

print(f"Base directory: {BASE_DIR}")
print(f"Client: {CLIENT}")
print(f"Mapping path: {MAPPING_PATH}")
print(f"Data path: {RAW_DATA_PATH}")"""
    })
    
    # ==================== SECTION 4: Mapping Loading ====================
    notebook_cells.append({
        "language": "markdown",
        "content": """## 4. Load Mapping Configuration

The mapping defines:
- `id_to_truck_model`: Maps each unit to a truck model
- `model_components`: Defines components, signals, criticality, and descriptions per truck model"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """# Load mapping
with open(MAPPING_PATH, 'r') as f:
    mapping = json.load(f)

id_to_truck_model = mapping['id_to_truck_model']
model_components = mapping['model_components']

print(f"Truck models: {list(model_components.keys())}")
print(f"Units: {list(id_to_truck_model.keys())}")
print(f"\\nComponents per model:")
for model, components in model_components.items():
    print(f"  {model}: {list(components.keys())}")"""
    })
    
    # ==================== SECTION 5: Data Loading ====================
    notebook_cells.append({
        "language": "markdown",
        "content": """## 5. Data Loading and Initial Cleaning"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """# Load raw data
df = pd.read_parquet(RAW_DATA_PATH)
df.sort_values([UNIT_COL, TIME_COL], inplace=True)
df.drop_duplicates(subset=[UNIT_COL, TIME_COL], keep='first', inplace=True)

# Drop problematic columns
columns_to_drop = ['Payload', 'EngOilFltr', 'AirFltr']
df.drop(columns=[col for col in columns_to_drop if col in df.columns], inplace=True)

print(f"Total rows: {len(df):,} ({len(df)/1e6:.2f}M)")
print(f"Date range: {df[TIME_COL].min()} to {df[TIME_COL].max()}")
print(f"Units: {df[UNIT_COL].nunique()}")
print(f"\\nColumns: {df.columns.tolist()}")
print(f"\\nMissing values (%):")
print(df.isna().sum()[df.isna().sum() > 0] / len(df) * 100)"""
    })
    
    # ==================== SECTION 6: Outlier Replacement ====================
    notebook_cells.append({
        "language": "markdown",
        "content": """## 6. Replace Outliers with NaN

Define acceptable ranges for each signal and replace out-of-range values with NaN."""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """# Define acceptable margins for each signal
margins = {
    # General
    'GPSLat': (-30.4, -30.1),
    'GPSLon': (-71.3, -70.9),
    'GPSElevation': (400, 2000),
    'GroundSpd': (0, 80),
    'EngSpd': (0, 2500),
    # Engine
    "EngCoolTemp": (30, 120),
    "RAftrclrTemp": (10, 100),
    "EngOilPres": (150, 700),
    "CnkcasePres": (-1.5, 1.5),
    "RtLtExhTemp": (-10, 10),
    "RtExhTemp": (150, 750),
    "LtExhTemp": (150, 750),
    # Transmission
    "DiffLubePres": (0, 800),
    "DiffTemp": (0, 150),
    "TrnLubeTemp": (-5, 120),
    "TCOutTemp": (30, 180),
    # Brakes
    "RtRBrkTemp": (20, 200),
    "RtFBrkTemp": (20, 200),
    "LtRBrkTemp": (20, 200),
    "LtFBrkTemp": (20, 200),
    # Direction
    'StrgOilTemp': (-10, 150),
}


def clean_outliers(df_in, margins):
    \"\"\"Replace out-of-range values with NaN.\"\"\"
    df = df_in.copy()
    for col, (lower, upper) in margins.items():
        if col in df.columns:
            df[col] = df[col].where((df[col] >= lower) & (df[col] <= upper), other=pd.NA)
    return df


df_cleaned = clean_outliers(df, margins)

# Identify numeric columns
num_cols = [col for col in margins.keys() if col in df_cleaned.columns]

# Drop rows with too many missing signals
df_cleaned.dropna(subset=num_cols, thresh=int(len(num_cols)/2), inplace=True)
df_cleaned.fillna({'EstadoMaquina': 'ND', 'EstadoCarga': 'Sin Carga'}, inplace=True)
df_cleaned.reset_index(drop=True, inplace=True)

print(f"Rows after outlier removal: {len(df_cleaned):,} ({len(df_cleaned)/1e6:.2f}M)")
print(f"\\nMissing values after cleaning (%):")
print(df_cleaned[num_cols].isna().sum() / len(df_cleaned) * 100)"""
    })
    
    # ==================== SECTION 7: Reindexing and Interpolation ====================
    notebook_cells.append({
        "language": "markdown",
        "content": """## 7. Reindex to 1-Minute Intervals and Interpolate

For each unit:
1. Reindex to a complete 1-minute time grid
2. Interpolate numeric signals (limited to max 10 consecutive missing values)
3. Forward/backward fill categorical features
4. Track interpolation metadata"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """def reindex_and_interpolate_unit(
    unit_df: pd.DataFrame,
    num_cols: list,
    cat_cols: list = ["EstadoMaquina", "EstadoCarga"],
    freq: str = "1min",
    interp_limit: int = 10
) -> pd.DataFrame:
    \"\"\"
    Reindex unit to 1-minute frequency and interpolate.
    
    Parameters:
    -----------
    unit_df : DataFrame with Unit and Fecha columns
    num_cols : List of numeric columns to interpolate
    cat_cols : List of categorical columns to forward/backward fill
    freq : Resampling frequency
    interp_limit : Maximum consecutive NaNs to interpolate
    
    Returns:
    --------
    DataFrame with additional metadata columns:
    - created_by_reindex: 1 if row was created by reindexing
    - imputed_any: 1 if any signal was imputed
    - n_imputed_signals: Count of imputed signals per row
    - time_gap_min: Time gap from previous row in minutes
    \"\"\"
    out = unit_df.copy().sort_values(TIME_COL).reset_index(drop=True)
    
    if out.empty:
        return out.copy()
    
    original_timestamps = set(out[TIME_COL])
    
    # Create full time index
    full_time_index = pd.date_range(
        start=out[TIME_COL].min(),
        end=out[TIME_COL].max(),
        freq=freq
    )
    
    out = out.set_index(TIME_COL).reindex(full_time_index)
    out.index.name = TIME_COL
    
    # Restore unit identifier
    out[UNIT_COL] = unit_df[UNIT_COL].iloc[0]
    
    # Fill categorical columns
    for c in cat_cols:
        if c in out.columns:
            out[c] = out[c].ffill().bfill()
    
    # Track positions before interpolation
    valid_cols = [c for c in num_cols if c in out.columns]
    before_na = out[valid_cols].isna()
    
    # Mark created rows
    out["created_by_reindex"] = (~out.index.isin(original_timestamps)).astype("int8")
    
    # Interpolate numeric columns
    out[valid_cols] = out[valid_cols].interpolate(
        method="time",
        limit=interp_limit,
        limit_area="inside"
    )
    
    # Track imputation
    out["imputed_any"] = ((before_na & ~out[valid_cols].isna()).any(axis=1)).astype("int8")
    out["n_imputed_signals"] = (before_na & ~out[valid_cols].isna()).sum(axis=1).astype("int16")
    
    # Calculate time gaps
    out["time_gap_min"] = (
        pd.Series(out.index, index=out.index).diff().dt.total_seconds().div(60)
    )
    
    return out.reset_index()


# Apply reindexing per unit
print("Reindexing and interpolating units...")
unit_results = []

for unit_id, unit_df in tqdm(df_cleaned.groupby(UNIT_COL, sort=False), desc="Processing units"):
    unit_out = reindex_and_interpolate_unit(
        unit_df=unit_df,
        num_cols=num_cols,
        freq="1min",
        interp_limit=10
    )
    unit_results.append(unit_out)

cleaned_df = pd.concat(unit_results, ignore_index=True) if unit_results else df_cleaned.head(0).copy()

print(f"\\nRows after reindexing: {len(cleaned_df):,} ({len(cleaned_df)/1e6:.2f}M)")
print(f"Created by reindex: {cleaned_df['created_by_reindex'].sum():,} ({cleaned_df['created_by_reindex'].mean()*100:.2f}%)")
print(f"Imputed rows: {cleaned_df['imputed_any'].sum():,} ({cleaned_df['imputed_any'].mean()*100:.2f}%)")
print(f"\\nMissing values (%):")
print(cleaned_df[num_cols].isna().sum() / len(cleaned_df) * 100)"""
    })
    
    # ==================== SECTION 8: Save Processed Data ====================
    notebook_cells.append({
        "language": "markdown",
        "content": """## 8. Persist Processed Data"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """# Save processed data
cleaned_df.to_parquet(PROCESSED_DATA_PATH, index=False)
print(f"Processed data saved to: {PROCESSED_DATA_PATH}")
print(f"File size: {PROCESSED_DATA_PATH.stat().st_size / 1e6:.2f} MB")"""
    })
    
    # ==================== SECTION 9: Service Classes ====================
    notebook_cells.append({
        "language": "markdown",
        "content": """## 9. Service Class Definitions

These classes encapsulate the business logic and are reusable across different contexts."""
    })
    
    notebook_cells.append({
        "language": "markdown",
        "content": """### 9.1 Helper Functions for Windowing"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """def _rolling_mean_1d(arr: np.ndarray, win: int) -> np.ndarray:
    \"\"\"Fast rolling mean for 1D array using cumsum.\"\"\"
    arr = np.asarray(arr, dtype=np.float64)
    c = np.empty(len(arr) + 1, dtype=np.float64)
    c[0] = 0.0
    np.cumsum(arr, out=c[1:])
    return (c[win:] - c[:-win]) / win


def _ensure_window_axis_order(x: np.ndarray, win: int) -> np.ndarray:
    \"\"\"Normalize sliding_window_view output to (n_windows, win, n_features).\"\"\"
    if x.ndim != 3:
        raise ValueError(f"Expected 3D array, got shape {x.shape}")
    if x.shape[1] == win:
        return x
    if x.shape[2] == win:
        return np.swapaxes(x, 1, 2)
    raise ValueError(f"Could not identify window axis in shape {x.shape}")


def _fill_by_unit_fast(arr_2d: np.ndarray, fill_value: float) -> np.ndarray:
    \"\"\"Fast fill for missing values per unit segment.\"\"\"
    df = pd.DataFrame(arr_2d)
    return df.ffill().bfill().fillna(fill_value).to_numpy()"""
    })
    
    notebook_cells.append({
        "language": "markdown",
        "content": """### 9.2 Windowing Configuration"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """@dataclass
class WindowingConfig:
    unit_col: str = UNIT_COL
    time_col: str = TIME_COL
    
    numeric_cols: Optional[List[str]] = None
    categorical_cols: Optional[List[str]] = None
    
    # Train windowing
    train_window_size: int = 60
    train_step_size: int = 1
    
    # Predict windowing
    predict_window_size: int = 60
    
    # Train filters
    min_numeric_coverage: float = 0.80
    min_row_coverage: float = 0.80
    max_created_fraction: Optional[float] = None
    max_imputed_fraction: Optional[float] = None
    
    # Fill values after scaling
    train_fill_value: float = 0.0
    predict_fill_value: float = -10.0
    
    output_dtype: str = "float32"""
    })
    
    notebook_cells.append({
        "language": "markdown",
        "content": """### 9.3 Preprocessing Service"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """class LSTMAutoencoderPreprocessor:
    \"\"\"
    Preprocessing service for LSTM autoencoder.
    
    Handles:
    - Numeric scaling (RobustScaler)
    - Categorical encoding (OneHotEncoder)
    - Train window generation (sliding windows with quality filters)
    - Predict window generation (hourly blocks)
    \"\"\"
    
    def __init__(self, config: WindowingConfig):
        self.config = config
        self.numeric_scaler = None
        self.ohe = None
        self.input_feature_names_: Optional[List[str]] = None
        self.target_feature_names_: Optional[List[str]] = None
        self.numeric_fill_values_: Optional[Dict[str, float]] = None
        self.is_fitted_: bool = False
    
    def fit(self, df: pd.DataFrame) -> "LSTMAutoencoderPreprocessor":
        \"\"\"Fit scalers and encoders on training data.\"\"\"
        df = self._validate_and_prepare_input(df)
        
        numeric_cols = self.config.numeric_cols or []
        categorical_cols = self.config.categorical_cols or []
        
        # Compute fill values
        self.numeric_fill_values_ = {
            col: df[col].median(skipna=True) if col in df.columns else 0.0
            for col in numeric_cols
        }
        
        # Fit numeric scaler
        self.numeric_scaler = RobustScaler()
        if numeric_cols:
            num_fit = df[numeric_cols].copy()
            for col in numeric_cols:
                num_fit[col] = num_fit[col].fillna(self.numeric_fill_values_[col])
            self.numeric_scaler.fit(num_fit)
        
        # Fit OHE
        self.ohe = OneHotEncoder(handle_unknown="ignore", drop="first", sparse_output=False)
        if categorical_cols:
            cat_fit = df[categorical_cols].copy().astype("string").fillna("__missing__")
            self.ohe.fit(cat_fit)
        
        self.target_feature_names_ = list(numeric_cols)
        self.input_feature_names_ = self._build_input_feature_names()
        
        self.is_fitted_ = True
        return self
    
    def transform_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        \"\"\"Transform rows: scale numerics, encode categoricals.\"\"\"
        self._check_is_fitted()
        df = self._validate_and_prepare_input(df)
        
        base_cols = [self.config.unit_col, self.config.time_col]
        extra_cols = [c for c in ["created_by_reindex", "imputed_any", "n_imputed_signals"] 
                      if c in df.columns]
        
        num_df = self._transform_numeric(df)
        cat_df = self._transform_categorical(df)
        
        out_parts = [df[base_cols + extra_cols].reset_index(drop=True)]
        if not num_df.empty:
            out_parts.append(num_df.reset_index(drop=True))
        if not cat_df.empty:
            out_parts.append(cat_df.reset_index(drop=True))
        
        return pd.concat(out_parts, axis=1, copy=False)
    
    def fit_transform_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        \"\"\"Fit and transform.\"\"\"
        self.fit(df)
        return self.transform_rows(df)
    
    def make_train_windows(
        self,
        raw_df: pd.DataFrame,
        transformed_df: pd.DataFrame,
        return_metadata: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, Optional[pd.DataFrame]]:
        \"\"\"Generate sliding train windows with quality filters.\"\"\"
        self._check_is_fitted()
        
        raw_df = self._validate_and_prepare_input(raw_df)
        transformed_df = transformed_df.copy()
        
        unit_col = self.config.unit_col
        time_col = self.config.time_col
        win = self.config.train_window_size
        step = self.config.train_step_size
        
        input_cols = self.input_feature_names_
        target_cols = self.target_feature_names_
        numeric_cols = self.config.numeric_cols or []
        
        # Ensure same ordering
        raw_df = raw_df.sort_values([unit_col, time_col]).reset_index(drop=True)
        transformed_df = transformed_df.sort_values([unit_col, time_col]).reset_index(drop=True)
        
        if len(raw_df) != len(transformed_df):
            raise ValueError("raw_df and transformed_df must have same length")
        
        unit_arr = raw_df[unit_col].to_numpy()
        time_arr = raw_df[time_col].to_numpy()
        
        raw_num = raw_df[numeric_cols].to_numpy(dtype=np.float32) if numeric_cols else np.empty((len(raw_df), 0), dtype=np.float32)
        X_all = transformed_df[input_cols].to_numpy(dtype=np.float32, copy=True)
        y_all = transformed_df[target_cols].to_numpy(dtype=np.float32, copy=True)
        
        created_arr = raw_df["created_by_reindex"].to_numpy(dtype=np.float32) if "created_by_reindex" in raw_df.columns else None
        imputed_arr = raw_df["imputed_any"].to_numpy(dtype=np.float32) if "imputed_any" in raw_df.columns else None
        
        # Find unit segments
        change = np.r_[True, unit_arr[1:] != unit_arr[:-1]]
        starts = np.flatnonzero(change)
        ends = np.r_[starts[1:], len(unit_arr)]
        
        X_seq = []
        y_seq = []
        meta_rows = []
        
        n_signals = len(numeric_cols)
        
        for s, e in zip(starts, ends):
            unit = unit_arr[s]
            n = e - s
            if n < win:
                continue
            
            X_u = X_all[s:e]
            y_u = y_all[s:e]
            raw_num_u = raw_num[s:e]
            time_u = time_arr[s:e]
            
            # Fill per unit
            X_u_filled = _fill_by_unit_fast(X_u, self.config.train_fill_value)
            y_u_filled = _fill_by_unit_fast(y_u, self.config.train_fill_value)
            
            # Create windows
            X_view = sliding_window_view(X_u_filled, window_shape=win, axis=0)
            y_view = sliding_window_view(y_u_filled, window_shape=win, axis=0)
            X_view = _ensure_window_axis_order(X_view, win)
            y_view = _ensure_window_axis_order(y_view, win)
            
            # Compute quality metrics
            if n_signals > 0:
                observed = ~np.isnan(raw_num_u)
                observed_count_per_row = observed.sum(axis=1).astype(np.float32)
                row_has_any = observed.any(axis=1).astype(np.float32)
                
                numeric_coverage = _rolling_mean_1d(observed_count_per_row, win) / n_signals
                row_coverage = _rolling_mean_1d(row_has_any, win)
            else:
                numeric_coverage = np.ones(n - win + 1, dtype=np.float32)
                row_coverage = np.ones(n - win + 1, dtype=np.float32)
            
            valid = (
                (numeric_coverage >= self.config.min_numeric_coverage) &
                (row_coverage >= self.config.min_row_coverage)
            )
            
            created_fraction = None
            if created_arr is not None:
                created_fraction = _rolling_mean_1d(created_arr[s:e], win)
                if self.config.max_created_fraction is not None:
                    valid &= (created_fraction <= self.config.max_created_fraction)
            
            imputed_fraction = None
            if imputed_arr is not None:
                imputed_fraction = _rolling_mean_1d(imputed_arr[s:e], win)
                if self.config.max_imputed_fraction is not None:
                    valid &= (imputed_fraction <= self.config.max_imputed_fraction)
            
            # Apply step
            idx = np.arange(0, n - win + 1, step)
            valid_idx = idx[valid[idx]]
            
            if len(valid_idx) == 0:
                continue
            
            X_sel = X_view[valid_idx]
            y_sel = y_view[valid_idx]
            
            # Safety check for infinites
            finite_mask = np.isfinite(X_sel).all(axis=(1, 2)) & np.isfinite(y_sel).all(axis=(1, 2))
            if not finite_mask.all():
                X_sel = X_sel[finite_mask]
                y_sel = y_sel[finite_mask]
                valid_idx = valid_idx[finite_mask]
            
            if len(valid_idx) == 0:
                continue
            
            X_seq.append(X_sel.astype(self.config.output_dtype))
            y_seq.append(y_sel.astype(self.config.output_dtype))
            
            if return_metadata:
                for start_idx in valid_idx:
                    row = {
                        "Unit": unit,
                        "window_type": "train_sliding",
                        "start_idx": int(start_idx),
                        "end_idx_exclusive": int(start_idx + win),
                        "start_time": time_u[start_idx],
                        "end_time": time_u[start_idx + win - 1],
                        "numeric_coverage": float(numeric_coverage[start_idx]),
                        "row_coverage": float(row_coverage[start_idx]),
                    }
                    if created_fraction is not None:
                        row["created_fraction"] = float(created_fraction[start_idx])
                    if imputed_fraction is not None:
                        row["imputed_fraction"] = float(imputed_fraction[start_idx])
                    meta_rows.append(row)
        
        X = np.concatenate(X_seq, axis=0).astype(self.config.output_dtype) if X_seq else np.empty((0, win, len(input_cols)), dtype=self.config.output_dtype)
        y = np.concatenate(y_seq, axis=0).astype(self.config.output_dtype) if y_seq else np.empty((0, win, len(target_cols)), dtype=self.config.output_dtype)
        
        meta = pd.DataFrame(meta_rows) if return_metadata else None
        return X, y, meta
    
    def make_predict_windows(
        self,
        raw_df: pd.DataFrame,
        transformed_df: pd.DataFrame,
        return_metadata: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, Optional[pd.DataFrame]]:
        \"\"\"Generate hour-block predict windows.\"\"\"
        self._check_is_fitted()
        
        raw_df = self._validate_and_prepare_input(raw_df)
        transformed_df = transformed_df.copy()
        
        unit_col = self.config.unit_col
        time_col = self.config.time_col
        win = self.config.predict_window_size
        
        input_cols = self.input_feature_names_
        target_cols = self.target_feature_names_
        
        raw_df = raw_df.sort_values([unit_col, time_col]).reset_index(drop=True)
        transformed_df = transformed_df.sort_values([unit_col, time_col]).reset_index(drop=True)
        
        if len(raw_df) != len(transformed_df):
            raise ValueError("raw_df and transformed_df must have same length")
        
        unit_arr = raw_df[unit_col].to_numpy()
        time_arr = raw_df[time_col].to_numpy()
        
        X_all = transformed_df[input_cols].to_numpy(dtype=np.float32, copy=True)
        y_all = transformed_df[target_cols].to_numpy(dtype=np.float32, copy=True)
        
        created_arr = raw_df["created_by_reindex"].to_numpy(dtype=np.float32) if "created_by_reindex" in raw_df.columns else None
        imputed_arr = raw_df["imputed_any"].to_numpy(dtype=np.float32) if "imputed_any" in raw_df.columns else None
        
        change = np.r_[True, unit_arr[1:] != unit_arr[:-1]]
        starts = np.flatnonzero(change)
        ends = np.r_[starts[1:], len(unit_arr)]
        
        X_seq = []
        y_seq = []
        meta_rows = []
        
        for s, e in zip(starts, ends):
            unit = unit_arr[s]
            n = e - s
            if n < win:
                continue
            
            n_complete_windows = n // win
            usable = n_complete_windows * win
            if usable == 0:
                continue
            
            X_u = X_all[s:s + usable]
            y_u = y_all[s:s + usable]
            time_u = time_arr[s:s + usable]
            
            X_u_filled = _fill_by_unit_fast(X_u, self.config.predict_fill_value)
            y_u_filled = _fill_by_unit_fast(y_u, self.config.predict_fill_value)
            
            X_blocks = X_u_filled.reshape(n_complete_windows, win, -1)
            y_blocks = y_u_filled.reshape(n_complete_windows, win, -1)
            
            finite_mask = np.isfinite(X_blocks).all(axis=(1, 2)) & np.isfinite(y_blocks).all(axis=(1, 2))
            if not finite_mask.all():
                X_blocks = X_blocks[finite_mask]
                y_blocks = y_blocks[finite_mask]
            
            if len(X_blocks) == 0:
                continue
            
            X_seq.append(X_blocks.astype(self.config.output_dtype))
            y_seq.append(y_blocks.astype(self.config.output_dtype))
            
            if return_metadata:
                for hour_idx in range(n_complete_windows):
                    start_idx = hour_idx * win
                    end_idx = start_idx + win
                    row = {
                        "Unit": unit,
                        "window_type": "predict_hour_block",
                        "hour_idx": hour_idx,
                        "start_idx": start_idx,
                        "end_idx_exclusive": end_idx,
                        "start_time": time_u[start_idx],
                        "end_time": time_u[end_idx - 1],
                        "n_rows": win,
                    }
                    if created_arr is not None:
                        row["created_fraction"] = float(created_arr[s + start_idx:s + end_idx].mean())
                    if imputed_arr is not None:
                        row["imputed_fraction"] = float(imputed_arr[s + start_idx:s + end_idx].mean())
                    meta_rows.append(row)
        
        X = np.concatenate(X_seq, axis=0).astype(self.config.output_dtype) if X_seq else np.empty((0, win, len(input_cols)), dtype=self.config.output_dtype)
        y = np.concatenate(y_seq, axis=0).astype(self.config.output_dtype) if y_seq else np.empty((0, win, len(target_cols)), dtype=self.config.output_dtype)
        
        meta = pd.DataFrame(meta_rows) if return_metadata else None
        return X, y, meta
    
    def fit_transform_train(
        self,
        df_train: pd.DataFrame,
        return_metadata: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame, Optional[pd.DataFrame]]:
        \"\"\"Fit, transform, and create train windows.\"\"\"
        tr_rows = self.fit_transform_rows(df_train)
        X, y, meta = self.make_train_windows(raw_df=df_train, transformed_df=tr_rows, return_metadata=return_metadata)
        return X, y, tr_rows, meta
    
    def transform_predict(
        self,
        df_test: pd.DataFrame,
        return_metadata: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame, Optional[pd.DataFrame]]:
        \"\"\"Transform and create predict windows.\"\"\"
        tr_rows = self.transform_rows(df_test)
        X, y, meta = self.make_predict_windows(raw_df=df_test, transformed_df=tr_rows, return_metadata=return_metadata)
        return X, y, tr_rows, meta
    
    def _validate_and_prepare_input(self, df: pd.DataFrame) -> pd.DataFrame:
        \"\"\"Validate and prepare input dataframe.\"\"\"
        df = df.copy()
        
        required_cols = [self.config.unit_col, self.config.time_col]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        if self.config.numeric_cols is None:
            raise ValueError("config.numeric_cols must be provided")
        
        if self.config.categorical_cols is None:
            self.config.categorical_cols = []
        
        if not pd.api.types.is_datetime64_any_dtype(df[self.config.time_col]):
            df[self.config.time_col] = pd.to_datetime(df[self.config.time_col], errors="coerce")
        
        df = df.dropna(subset=[self.config.unit_col, self.config.time_col])
        df = df.sort_values([self.config.unit_col, self.config.time_col]).reset_index(drop=True)
        
        for col in self.config.numeric_cols:
            if col in df.columns and (df[col].dtype == "object" or pd.api.types.is_string_dtype(df[col])):
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        for col in self.config.categorical_cols:
            if col in df.columns:
                df[col] = df[col].astype("string")
        
        return df
    
    def _transform_numeric(self, df: pd.DataFrame) -> pd.DataFrame:
        \"\"\"Scale numeric columns, preserving NaNs.\"\"\"
        numeric_cols = self.config.numeric_cols or []
        if not numeric_cols:
            return pd.DataFrame(index=df.index)
        
        num_df = df[numeric_cols].copy()
        nan_mask = num_df.isna()
        
        fill_values = self.numeric_fill_values_ or {c: 0.0 for c in numeric_cols}
        num_temp = num_df.copy()
        for c in numeric_cols:
            num_temp[c] = num_temp[c].fillna(fill_values.get(c, 0.0))
        
        scaled = pd.DataFrame(
            self.numeric_scaler.transform(num_temp),
            columns=numeric_cols,
            index=df.index
        )
        
        # Restore NaNs
        scaled[nan_mask] = np.nan
        return scaled
    
    def _transform_categorical(self, df: pd.DataFrame) -> pd.DataFrame:
        \"\"\"Encode categorical columns.\"\"\"
        categorical_cols = self.config.categorical_cols or []
        if not categorical_cols:
            return pd.DataFrame(index=df.index)
        
        cat_df = df[categorical_cols].copy().astype("string").fillna("__missing__")
        arr = self.ohe.transform(cat_df)
        cols = self.ohe.get_feature_names_out(categorical_cols).tolist()
        return pd.DataFrame(arr, columns=cols, index=df.index)
    
    def _build_input_feature_names(self) -> List[str]:
        \"\"\"Build list of input feature names.\"\"\"
        names = list(self.config.numeric_cols or [])
        if self.config.categorical_cols:
            names.extend(self.ohe.get_feature_names_out(self.config.categorical_cols).tolist())
        return names
    
    def _check_is_fitted(self):
        \"\"\"Check if preprocessor is fitted.\"\"\"
        if not self.is_fitted_:
            raise RuntimeError("Preprocessor not fitted. Call fit() first.")"""
    })
    
    notebook_cells.append({
        "language": "markdown",
        "content": """### 9.4 Model Configuration"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """@dataclass
class LSTMAEModelConfig:
    latent_dim: int = 8
    encoder_lstm_1: int = 32
    encoder_lstm_2: int = 16
    decoder_lstm_1: int = 16
    decoder_lstm_2: int = 32
    
    dropout_rate: float = 0.2
    learning_rate: float = 1e-3
    
    batch_size: int = 32
    epochs: int = 50
    validation_split: float = 0.2
    early_stopping_patience: int = 5
    
    loss: str = "mse"
    metrics: tuple = ()"""
    })
    
    notebook_cells.append({
        "language": "markdown",
        "content": """### 9.5 Model Service"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """class LSTMAutoencoderService:
    \"\"\"
    Service for LSTM autoencoder model.
    
    Handles:
    - Model building
    - Training with early stopping
    - Prediction
    - Save/load artifacts
    - Reconstruction error computation
    \"\"\"
    
    def __init__(
        self,
        preprocessor: LSTMAutoencoderPreprocessor,
        model_config: LSTMAEModelConfig,
        model: Optional[tf.keras.Model] = None
    ):
        self.preprocessor = preprocessor
        self.model_config = model_config
        self.model = model
        self.history_ = None
    
    def build_model(self) -> tf.keras.Model:
        \"\"\"Build LSTM autoencoder architecture.\"\"\"
        if not self.preprocessor.is_fitted_:
            raise RuntimeError("Preprocessor must be fitted first")
        
        seq_len = self.preprocessor.config.train_window_size
        n_input = len(self.preprocessor.input_feature_names_)
        n_output = len(self.preprocessor.target_feature_names_)
        
        cfg = self.model_config
        
        # Encoder
        encoder_inputs = layers.Input(shape=(seq_len, n_input), name="encoder_inputs")
        x = layers.Masking(mask_value=self.preprocessor.config.predict_fill_value)(encoder_inputs)
        x = layers.LSTM(cfg.encoder_lstm_1, return_sequences=True, name="enc_lstm_1")(x)
        x = layers.Dropout(cfg.dropout_rate, name="enc_dropout_1")(x)
        x = layers.LSTM(cfg.encoder_lstm_2, return_sequences=False, name="enc_lstm_2")(x)
        x = layers.Dropout(cfg.dropout_rate, name="enc_dropout_2")(x)
        
        # Latent
        latent = layers.Dense(cfg.latent_dim, activation="linear", name="latent_vector")(x)
        
        # Decoder
        x = layers.RepeatVector(seq_len, name="repeat_vector")(latent)
        x = layers.LSTM(cfg.decoder_lstm_1, return_sequences=True, name="dec_lstm_1")(x)
        x = layers.Dropout(cfg.dropout_rate, name="dec_dropout_1")(x)
        x = layers.LSTM(cfg.decoder_lstm_2, return_sequences=True, name="dec_lstm_2")(x)
        
        decoder_outputs = layers.TimeDistributed(
            layers.Dense(n_output),
            name="reconstructed_numeric"
        )(x)
        
        model = Model(encoder_inputs, decoder_outputs, name="lstm_autoencoder")
        optimizer = tf.keras.optimizers.Adam(learning_rate=cfg.learning_rate)
        model.compile(optimizer=optimizer, loss=cfg.loss, metrics=list(cfg.metrics))
        
        self.model = model
        return model
    
    def fit(self, df_train: pd.DataFrame, verbose: int = 1) -> Dict[str, Any]:
        \"\"\"Fit preprocessor and train model.\"\"\"
        X_train, y_train, transformed_rows, train_meta = self.preprocessor.fit_transform_train(df_train, return_metadata=True)
        
        if X_train.shape[0] == 0:
            raise ValueError("No valid training windows generated")
        
        if self.model is None:
            self.build_model()
        
        callbacks = [
            tf.keras.callbacks.EarlyStopping(
                patience=self.model_config.early_stopping_patience,
                restore_best_weights=True,
                monitor="val_loss"
            )
        ]
        
        history = self.model.fit(
            X_train, y_train,
            epochs=self.model_config.epochs,
            batch_size=self.model_config.batch_size,
            validation_split=self.model_config.validation_split,
            callbacks=callbacks,
            verbose=verbose,
            shuffle=True
        )
        
        self.history_ = history.history
        
        return {
            "X_train_shape": X_train.shape,
            "y_train_shape": y_train.shape,
            "n_train_windows": int(X_train.shape[0]),
            "history": self.history_,
            "train_meta": train_meta,
            "transformed_rows": transformed_rows,
        }
    
    def predict_windows(
        self,
        df_test: pd.DataFrame,
        return_reconstruction: bool = True
    ) -> Dict[str, Any]:
        \"\"\"Predict and compute reconstruction errors.\"\"\"
        if self.model is None:
            raise RuntimeError("Model not loaded/built")
        
        X_pred, y_true, transformed_rows, pred_meta = self.preprocessor.transform_predict(df_test, return_metadata=True)
        
        if X_pred.shape[0] == 0:
            return {
                "X_pred": X_pred,
                "y_true": y_true,
                "y_pred": np.empty_like(y_true),
                "pred_meta": pred_meta,
                "window_errors": pd.DataFrame(),
                "signal_errors": pd.DataFrame(),
                "transformed_rows": transformed_rows,
            }
        
        y_pred = self.model.predict(X_pred, verbose=0)
        
        window_errors_df, signal_errors_df = self._compute_reconstruction_errors(y_true, y_pred, pred_meta)
        
        result = {
            "X_pred": X_pred,
            "y_true": y_true,
            "y_pred": y_pred,
            "pred_meta": pred_meta,
            "window_errors": window_errors_df,
            "signal_errors": signal_errors_df,
            "transformed_rows": transformed_rows,
        }
        
        if not return_reconstruction:
            result.pop("X_pred", None)
            result.pop("y_true", None)
            result.pop("y_pred", None)
        
        return result
    
    def _compute_reconstruction_errors(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        pred_meta: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        \"\"\"Compute per-window and per-signal reconstruction errors.\"\"\"
        signal_names = self.preprocessor.target_feature_names_
        
        abs_err = np.abs(y_true - y_pred)
        sq_err = np.square(y_true - y_pred)
        
        # Window-level
        window_mae = abs_err.mean(axis=(1, 2))
        window_mse = sq_err.mean(axis=(1, 2))
        window_rmse = np.sqrt(window_mse)
        
        window_errors_df = pred_meta.copy()
        window_errors_df["window_mae"] = window_mae
        window_errors_df["window_mse"] = window_mse
        window_errors_df["window_rmse"] = window_rmse
        
        # Signal-level
        signal_mae = abs_err.mean(axis=1)
        signal_mse = sq_err.mean(axis=1)
        signal_rmse = np.sqrt(signal_mse)
        
        signal_error_rows = []
        for i in range(len(pred_meta)):
            base = pred_meta.iloc[i].to_dict()
            for j, sig in enumerate(signal_names):
                signal_error_rows.append({
                    **base,
                    "signal": sig,
                    "signal_mae": float(signal_mae[i, j]),
                    "signal_mse": float(signal_mse[i, j]),
                    "signal_rmse": float(signal_rmse[i, j]),
                })
        
        signal_errors_df = pd.DataFrame(signal_error_rows)
        return window_errors_df, signal_errors_df
    
    def save(self, artifact_dir: str) -> None:
        \"\"\"Save model and artifacts.\"\"\"
        if self.model is None:
            raise RuntimeError("No model to save")
        
        os.makedirs(artifact_dir, exist_ok=True)
        
        # Save model
        self.model.save(os.path.join(artifact_dir, "model.keras"))
        
        # Save preprocessor
        joblib.dump(self.preprocessor, os.path.join(artifact_dir, "preprocessor.joblib"))
        
        # Save config
        with open(os.path.join(artifact_dir, "model_config.json"), "w") as f:
            json.dump(asdict(self.model_config), f, indent=2)
        
        # Save metadata
        metadata = {
            "input_feature_names": self.preprocessor.input_feature_names_,
            "target_feature_names": self.preprocessor.target_feature_names_,
            "train_window_size": self.preprocessor.config.train_window_size,
            "predict_window_size": self.preprocessor.config.predict_window_size,
        }
        with open(os.path.join(artifact_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2)
    
    @classmethod
    def load(cls, artifact_dir: str) -> "LSTMAutoencoderService":
        \"\"\"Load saved model and artifacts.\"\"\"
        model = tf.keras.models.load_model(os.path.join(artifact_dir, "model.keras"))
        preprocessor = joblib.load(os.path.join(artifact_dir, "preprocessor.joblib"))
        
        with open(os.path.join(artifact_dir, "model_config.json"), "r") as f:
            cfg_dict = json.load(f)
        
        return cls(
            preprocessor=preprocessor,
            model_config=LSTMAEModelConfig(**cfg_dict),
            model=model
        )"""
    })
    
    notebook_cells.append({
        "language": "markdown",
        "content": """### 9.6 Health Index Configuration"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """@dataclass
class HealthIndexConfig:
    alpha: float = 1.0
    time_agg: str = "mean"  # mean, median, max, p95
    signal_agg: str = "rms"  # mean, rms, max
    unit_agg: str = "mean"  # mean, median, min, p10
    percentile_low: int = 50
    percentile_high: int = 95
    eps: float = 1e-8"""
    })
    
    notebook_cells.append({
        "language": "markdown",
        "content": """### 9.7 Health Index Service"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """class HealthIndexService:
    \"\"\"
    Service for Health Index computation.
    
    Handles:
    - Computing reference error statistics from training data
    - Normalizing reconstruction errors
    - Computing Health Index scores
    - Consolidating results per unit/time
    - Save/load artifacts
    \"\"\"
    
    def __init__(
        self,
        signal_cols: List[str],
        config: Optional[HealthIndexConfig] = None,
        error_stats: Optional[Dict[str, Dict[str, float]]] = None,
    ):
        self.signal_cols = signal_cols
        self.config = config or HealthIndexConfig()
        self.error_stats = error_stats
    
    def fit_error_stats(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Dict[str, float]]:
        \"\"\"Compute per-signal reference percentiles from training reconstruction errors.\"\"\"
        if y_true.shape != y_pred.shape:
            raise ValueError("y_true and y_pred must have same shape")
        
        if y_true.shape[-1] != len(self.signal_cols):
            raise ValueError("signal_cols length mismatch")
        
        abs_err = np.abs(y_true - y_pred)
        
        p_low = self.config.percentile_low
        p_high = self.config.percentile_high
        
        stats = {}
        for j, sig in enumerate(self.signal_cols):
            sig_err = abs_err[:, :, j].reshape(-1)
            
            stats[sig] = {
                f"p{p_low}": float(np.percentile(sig_err, p_low)),
                f"p{p_high}": float(np.percentile(sig_err, p_high)),
                "mean": float(np.mean(sig_err)),
                "std": float(np.std(sig_err)),
                "min": float(np.min(sig_err)),
                "max": float(np.max(sig_err)),
                "n": int(sig_err.shape[0]),
            }
        
        self.error_stats = stats
        return stats
    
    def save(self, artifact_dir: str) -> None:
        \"\"\"Save Health Index configuration and error statistics.\"\"\"
        if self.error_stats is None:
            raise RuntimeError("error_stats not fitted")
        
        os.makedirs(artifact_dir, exist_ok=True)
        
        with open(os.path.join(artifact_dir, "health_index_config.json"), "w") as f:
            json.dump(asdict(self.config), f, indent=2)
        
        with open(os.path.join(artifact_dir, "error_stats.json"), "w") as f:
            json.dump(self.error_stats, f, indent=2)
        
        with open(os.path.join(artifact_dir, "signal_cols.json"), "w") as f:
            json.dump(self.signal_cols, f, indent=2)
    
    @classmethod
    def load(cls, artifact_dir: str) -> "HealthIndexService":
        \"\"\"Load saved Health Index artifacts.\"\"\"
        with open(os.path.join(artifact_dir, "health_index_config.json"), "r") as f:
            config = HealthIndexConfig(**json.load(f))
        
        with open(os.path.join(artifact_dir, "error_stats.json"), "r") as f:
            error_stats = json.load(f)
        
        with open(os.path.join(artifact_dir, "signal_cols.json"), "r") as f:
            signal_cols = json.load(f)
        
        return cls(signal_cols=signal_cols, config=config, error_stats=error_stats)
    
    def score_windows(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        pred_meta: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        \"\"\"
        Score windows and return:
        - signal_window_df: per-window per-signal scores
        - window_hi_df: per-window Health Index
        - unit_hi_df: per-unit aggregated Health Index
        \"\"\"
        if self.error_stats is None:
            raise RuntimeError("error_stats not available. Fit or load first.")
        
        if y_true.shape != y_pred.shape:
            raise ValueError("y_true and y_pred must have same shape")
        
        if y_true.shape[0] != len(pred_meta):
            raise ValueError("pred_meta must have one row per window")
        
        if y_true.shape[-1] != len(self.signal_cols):
            raise ValueError("signal_cols length mismatch")
        
        abs_err = np.abs(y_true - y_pred)
        n_windows, seq_len, n_signals = abs_err.shape
        
        def agg_time(arr, method: str):
            if method == "mean":
                return float(np.mean(arr))
            elif method == "median":
                return float(np.median(arr))
            elif method == "max":
                return float(np.max(arr))
            elif method == "p95":
                return float(np.percentile(arr, 95))
            else:
                raise ValueError("Invalid time_agg")
        
        def agg_signals(arr, method: str):
            if method == "mean":
                return float(np.mean(arr))
            elif method == "rms":
                return float(np.sqrt(np.mean(np.square(arr))))
            elif method == "max":
                return float(np.max(arr))
            else:
                raise ValueError("Invalid signal_agg")
        
        def agg_unit(series: pd.Series, method: str):
            if method == "mean":
                return series.mean()
            elif method == "median":
                return series.median()
            elif method == "min":
                return series.min()
            elif method == "p10":
                return series.quantile(0.10)
            else:
                raise ValueError("Invalid unit_agg")
        
        p_low = self.config.percentile_low
        p_high = self.config.percentile_high
        eps = self.config.eps
        
        signal_rows = []
        window_rows = []
        
        for i in range(n_windows):
            base_meta = pred_meta.iloc[i].to_dict()
            
            norm_vals_window = []
            raw_vals_window = []
            
            for j, sig in enumerate(self.signal_cols):
                sig_stats = self.error_stats[sig]
                low = sig_stats[f"p{p_low}"]
                high = sig_stats[f"p{p_high}"]
                
                if high <= low:
                    raise ValueError(f"Invalid error stats for signal '{sig}'")
                
                err_ts = abs_err[i, :, j]
                norm_ts = np.clip((err_ts - low) / (high - low + eps), a_min=0.0, a_max=None)
                
                raw_err = agg_time(err_ts, self.config.time_agg)
                norm_err = agg_time(norm_ts, self.config.time_agg)
                
                raw_vals_window.append(raw_err)
                norm_vals_window.append(norm_err)
                
                signal_rows.append({
                    **base_meta,
                    "signal": sig,
                    "recon_error_raw": raw_err,
                    "recon_error_norm": norm_err,
                    f"p{p_low}_ref": low,
                    f"p{p_high}_ref": high,
                })
            
            reconstruction_error_raw = agg_signals(np.array(raw_vals_window), self.config.signal_agg)
            reconstruction_error_score = agg_signals(np.array(norm_vals_window), self.config.signal_agg)
            health_index_window = float(np.exp(-self.config.alpha * reconstruction_error_score))
            
            window_rows.append({
                **base_meta,
                "reconstruction_error_raw": reconstruction_error_raw,
                "reconstruction_error_score": reconstruction_error_score,
                "health_index": health_index_window,
                "n_signals": n_signals,
                "window_size": seq_len,
            })
        
        signal_window_df = pd.DataFrame(signal_rows)
        window_hi_df = pd.DataFrame(window_rows)
        
        unit_col = "Unit" if "Unit" in window_hi_df.columns else "unit"
        
        unit_hi_df = (
            window_hi_df.groupby(unit_col, as_index=False)
            .agg(
                health_index=("health_index", lambda s: agg_unit(s, self.config.unit_agg)),
                reconstruction_error=("reconstruction_error_score", lambda s: agg_unit(s, self.config.unit_agg)),
                n_windows=("health_index", "count"),
                start_time=("start_time", "min"),
                end_time=("end_time", "max"),
            )
        )
        
        return signal_window_df, window_hi_df, unit_hi_df
    
    def consolidate_window_health_index(
        self,
        window_hi_df: pd.DataFrame,
        unit_col: str = "Unit",
        start_col: str = "start_time",
        end_col: str = "end_time",
        hi_col: str = "health_index",
    ) -> pd.DataFrame:
        \"\"\"Return compact dataframe: unit, start_time, end_time, health_index.\"\"\"
        cols = [unit_col, start_col, end_col, hi_col]
        optional_cols = [
            c for c in ["hour_idx", "reconstruction_error_score", "created_fraction", "imputed_fraction"]
            if c in window_hi_df.columns
        ]
        return window_hi_df[cols + optional_cols].copy()"""
    })
    
    # ==================== SECTION 10: Optuna + MLflow Integration ====================
    notebook_cells.append({
        "language": "markdown",
        "content": """## 10. Hyperparameter Optimization with Optuna + MLflow"""
    })
    
    notebook_cells.append({
        "language": "markdown",
        "content": """### 10.1 MLflow Setup"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """# Configure MLflow (no SQLite backend)
MLFLOW_TRACKING_DIR = BASE_DIR / "mlruns"
MLFLOW_TRACKING_DIR.mkdir(exist_ok=True)

mlflow.set_tracking_uri(f"file:///{MLFLOW_TRACKING_DIR.as_posix()}")

print(f"MLflow tracking URI: {mlflow.get_tracking_uri()}")"""
    })
    
    notebook_cells.append({
        "language": "markdown",
        "content": """### 10.2 Optuna Objective Function"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """def create_optuna_objective(
    df_train: pd.DataFrame,
    component: str,
    signal_cols: List[str],
    window_size: int,
    experiment_name: str
):
    \"\"\"
    Create Optuna objective function for hyperparameter tuning.
    
    Parameters:
    -----------
    df_train : Training data
    component : Component name (e.g., 'Motor', 'Frenos')
    signal_cols : List of signal columns for this component
    window_size : Window size for training
    experiment_name : MLflow experiment name
    
    Returns:
    --------
    Objective function for Optuna
    \"\"\"
    
    def objective(trial: optuna.Trial) -> float:
        # Suggest hyperparameters
        latent_dim = trial.suggest_int("latent_dim", 2, 16)
        encoder_lstm_1 = trial.suggest_int("encoder_lstm_1", 8, 64, step=8)
        encoder_lstm_2 = trial.suggest_int("encoder_lstm_2", 4, 32, step=4)
        decoder_lstm_1 = trial.suggest_int("decoder_lstm_1", 4, 32, step=4)
        decoder_lstm_2 = trial.suggest_int("decoder_lstm_2", 8, 64, step=8)
        dropout_rate = trial.suggest_float("dropout_rate", 0.1, 0.4)
        learning_rate = trial.suggest_float("learning_rate", 1e-4, 1e-2, log=True)
        batch_size = trial.suggest_categorical("batch_size", [16, 32, 64, 128])
        
        min_numeric_coverage = trial.suggest_float("min_numeric_coverage", 0.75, 0.95)
        min_row_coverage = trial.suggest_float("min_row_coverage", 0.85, 0.98)
        max_created_fraction = trial.suggest_float("max_created_fraction", 0.05, 0.15)
        max_imputed_fraction = trial.suggest_float("max_imputed_fraction", 0.15, 0.35)
        
        # Start MLflow run
        with mlflow.start_run(run_name=f"trial_{trial.number}", nested=True):
            # Log hyperparameters
            mlflow.log_params({
                "component": component,
                "window_size": window_size,
                "latent_dim": latent_dim,
                "encoder_lstm_1": encoder_lstm_1,
                "encoder_lstm_2": encoder_lstm_2,
                "decoder_lstm_1": decoder_lstm_1,
                "decoder_lstm_2": decoder_lstm_2,
                "dropout_rate": dropout_rate,
                "learning_rate": learning_rate,
                "batch_size": batch_size,
                "min_numeric_coverage": min_numeric_coverage,
                "min_row_coverage": min_row_coverage,
                "max_created_fraction": max_created_fraction,
                "max_imputed_fraction": max_imputed_fraction,
            })
            
            try:
                # Create configuration
                windowing_config = WindowingConfig(
                    unit_col=UNIT_COL,
                    time_col=TIME_COL,
                    numeric_cols=signal_cols,
                    categorical_cols=["EstadoMaquina", "EstadoCarga"],
                    train_window_size=window_size,
                    train_step_size=1,
                    predict_window_size=window_size,
                    min_numeric_coverage=min_numeric_coverage,
                    min_row_coverage=min_row_coverage,
                    max_created_fraction=max_created_fraction,
                    max_imputed_fraction=max_imputed_fraction,
                    train_fill_value=0.0,
                    predict_fill_value=-10.0,
                )
                
                model_config = LSTMAEModelConfig(
                    latent_dim=latent_dim,
                    encoder_lstm_1=encoder_lstm_1,
                    encoder_lstm_2=encoder_lstm_2,
                    decoder_lstm_1=decoder_lstm_1,
                    decoder_lstm_2=decoder_lstm_2,
                    dropout_rate=dropout_rate,
                    learning_rate=learning_rate,
                    batch_size=batch_size,
                    epochs=50,
                    validation_split=0.2,
                    early_stopping_patience=5,
                )
                
                # Create preprocessor and service
                preprocessor = LSTMAutoencoderPreprocessor(windowing_config)
                service = LSTMAutoencoderService(preprocessor, model_config)
                
                # Train
                train_result = service.fit(df_train, verbose=0)
                
                # Get best validation loss
                val_loss = min(service.history_["val_loss"])
                
                # Log metrics
                mlflow.log_metrics({
                    "val_loss": val_loss,
                    "n_train_windows": train_result["n_train_windows"],
                    "final_train_loss": service.history_["loss"][-1],
                    "epochs_trained": len(service.history_["loss"]),
                })
                
                # Report to Optuna for pruning
                trial.report(val_loss, step=len(service.history_["loss"]))
                
                if trial.should_prune():
                    mlflow.log_param("pruned", True)
                    raise optuna.TrialPruned()
                
                mlflow.log_param("pruned", False)
                
                return val_loss
                
            except Exception as e:
                mlflow.log_param("error", str(e))
                print(f"Trial {trial.number} failed: {e}")
                raise
    
    return objective"""
    })
    
    notebook_cells.append({
        "language": "markdown",
        "content": """### 10.3 Run Optimization"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """def run_hyperparameter_optimization(
    df_train: pd.DataFrame,
    component: str,
    signal_cols: List[str],
    window_size: int = 60,
    n_trials: int = 50,
    timeout: int = 3600
) -> Tuple[optuna.Study, Dict[str, Any]]:
    \"\"\"
    Run Optuna hyperparameter optimization with MLflow tracking.
    
    Parameters:
    -----------
    df_train : Training data
    component : Component name
    signal_cols : List of signal columns
    window_size : Window size
    n_trials : Number of Optuna trials
    timeout : Timeout in seconds
    
    Returns:
    --------
    study : Optuna study object
    best_params : Dictionary of best parameters
    \"\"\"
    # Create experiment name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    experiment_name = f"{component}_{window_size}_{timestamp}"
    
    # Set MLflow experiment
    mlflow.set_experiment(experiment_name)
    
    print(f"Starting optimization for {component}")
    print(f"Experiment: {experiment_name}")
    print(f"Signals: {signal_cols}")
    print(f"Window size: {window_size}")
    print(f"Max trials: {n_trials}")
    print(f"Timeout: {timeout}s")
    
    # Create study
    study = optuna.create_study(
        direction="minimize",
        sampler=TPESampler(seed=42),
        pruner=MedianPruner(n_startup_trials=5, n_warmup_steps=10),
        study_name=experiment_name,
    )
    
    # Create objective
    objective = create_optuna_objective(
        df_train=df_train,
        component=component,
        signal_cols=signal_cols,
        window_size=window_size,
        experiment_name=experiment_name
    )
    
    # Run optimization
    with mlflow.start_run(run_name="optimization_summary"):
        mlflow.log_params({
            "component": component,
            "window_size": window_size,
            "n_trials": n_trials,
            "timeout": timeout,
        })
        
        study.optimize(
            objective,
            n_trials=n_trials,
            timeout=timeout,
            show_progress_bar=True
        )
        
        # Log best results
        best_params = study.best_params
        best_value = study.best_value
        
        mlflow.log_params({f"best_{k}": v for k, v in best_params.items()})
        mlflow.log_metric("best_val_loss", best_value)
        
        # Save study
        study_path = CLIENT_MODELS_DIR / component / "optuna_study.pkl"
        study_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(study, study_path)
        mlflow.log_artifact(study_path)
        
        # Save best params
        best_params_path = CLIENT_MODELS_DIR / component / "best_params.json"
        with open(best_params_path, "w") as f:
            json.dump(best_params, f, indent=2)
        mlflow.log_artifact(best_params_path)
    
    print(f"\\n✓ Optimization complete!")
    print(f"Best validation loss: {best_value:.6f}")
    print(f"Best parameters: {best_params}")
    
    return study, best_params"""
    })
    
    # ==================== SECTION 11: Mapping-Driven Orchestration ====================
    notebook_cells.append({
        "language": "markdown",
        "content": """## 11. Mapping-Driven Pipeline Orchestration

This section orchestrates the complete pipeline using the mapping configuration.
It processes each component for all applicable units."""
    })
    
    notebook_cells.append({
        "language": "markdown",
        "content": """### 11.1 Train/Test Split"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """# Load processed data
if PROCESSED_DATA_PATH.exists():
    df_processed = pd.read_parquet(PROCESSED_DATA_PATH)
    print(f"Loaded processed data: {len(df_processed):,} rows")
else:
    # Use cleaned_df from previous steps
    df_processed = cleaned_df
    print(f"Using in-memory processed data: {len(df_processed):,} rows")

# Define train/test split
WEEKS_TO_TEST = 8
split_date = df_processed[TIME_COL].max() - pd.Timedelta(weeks=WEEKS_TO_TEST)

df_train_full = df_processed[df_processed[TIME_COL] < split_date].copy()
df_test_full = df_processed[df_processed[TIME_COL] >= split_date].copy()

print(f"\\nTrain data: {len(df_train_full):,} rows ({df_train_full[TIME_COL].min()} to {df_train_full[TIME_COL].max()})")
print(f"Test data: {len(df_test_full):,} rows ({df_test_full[TIME_COL].min()} to {df_test_full[TIME_COL].max()})")"""
    })
    
    notebook_cells.append({
        "language": "markdown",
        "content": """### 11.2 Component Pipeline Function"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """def process_component(
    component_name: str,
    signal_cols: List[str],
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    window_size: int = 60,
    run_optimization: bool = False,
    n_trials: int = 20,
    use_best_params: bool = True,
) -> Dict[str, Any]:
    \"\"\"
    Process a single component through the complete pipeline.
    
    Steps:
    1. (Optional) Run Optuna hyperparameter optimization
    2. Create preprocessor and model service
    3. Train model
    4. Save model artifacts
    5. Run inference on test data
    6. Compute Health Index
    7. Save Health Index artifacts
    8. Return consolidated results
    
    Parameters:
    -----------
    component_name : Component name (e.g., 'Motor', 'Frenos')
    signal_cols : List of signal columns for this component
    df_train : Training data
    df_test : Test data
    window_size : Window size for training
    run_optimization : Whether to run Optuna optimization
    n_trials : Number of Optuna trials
    use_best_params : Whether to use best params from previous optimization
    
    Returns:
    --------
    Dictionary containing:
    - window_hi_df: Window-level Health Index
    - unit_hi_df: Unit-level aggregated Health Index
    - signal_window_df: Per-signal per-window scores
    - model_artifacts_path: Path to saved model
    - hi_artifacts_path: Path to saved Health Index artifacts
    \"\"\"
    print(f"\\n{'='*80}")
    print(f"Processing component: {component_name}")
    print(f"Signals: {signal_cols}")
    print(f"{'='*80}")
    
    component_dir = CLIENT_MODELS_DIR / component_name
    component_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Optuna optimization (optional)
    best_params = None
    if run_optimization:
        print(f"\\n[1/7] Running hyperparameter optimization...")
        study, best_params = run_hyperparameter_optimization(
            df_train=df_train,
            component=component_name,
            signal_cols=signal_cols,
            window_size=window_size,
            n_trials=n_trials,
            timeout=3600
        )
    elif use_best_params:
        best_params_path = component_dir / "best_params.json"
        if best_params_path.exists():
            with open(best_params_path, "r") as f:
                best_params = json.load(f)
            print(f"\\n[1/7] Loaded best params from {best_params_path}")
        else:
            print(f"\\n[1/7] No best params found, using defaults")
    
    # Step 2: Create configuration
    print(f"\\n[2/7] Creating preprocessor and model configuration...")
    
    if best_params:
        windowing_config = WindowingConfig(
            unit_col=UNIT_COL,
            time_col=TIME_COL,
            numeric_cols=signal_cols,
            categorical_cols=["EstadoMaquina", "EstadoCarga"],
            train_window_size=window_size,
            train_step_size=1,
            predict_window_size=window_size,
            min_numeric_coverage=best_params.get("min_numeric_coverage", 0.85),
            min_row_coverage=best_params.get("min_row_coverage", 0.95),
            max_created_fraction=best_params.get("max_created_fraction", 0.08),
            max_imputed_fraction=best_params.get("max_imputed_fraction", 0.22),
            train_fill_value=0.0,
            predict_fill_value=-10.0,
        )
        
        model_config = LSTMAEModelConfig(
            latent_dim=best_params.get("latent_dim", 8),
            encoder_lstm_1=best_params.get("encoder_lstm_1", 32),
            encoder_lstm_2=best_params.get("encoder_lstm_2", 16),
            decoder_lstm_1=best_params.get("decoder_lstm_1", 16),
            decoder_lstm_2=best_params.get("decoder_lstm_2", 32),
            dropout_rate=best_params.get("dropout_rate", 0.2),
            learning_rate=best_params.get("learning_rate", 1e-3),
            batch_size=best_params.get("batch_size", 32),
            epochs=50,
            validation_split=0.2,
            early_stopping_patience=5,
        )
    else:
        # Default configuration
        windowing_config = WindowingConfig(
            unit_col=UNIT_COL,
            time_col=TIME_COL,
            numeric_cols=signal_cols,
            categorical_cols=["EstadoMaquina", "EstadoCarga"],
            train_window_size=window_size,
            train_step_size=1,
            predict_window_size=window_size,
            min_numeric_coverage=0.85,
            min_row_coverage=0.95,
            max_created_fraction=0.08,
            max_imputed_fraction=0.22,
            train_fill_value=0.0,
            predict_fill_value=-10.0,
        )
        
        model_config = LSTMAEModelConfig(
            latent_dim=8,
            encoder_lstm_1=32,
            encoder_lstm_2=16,
            decoder_lstm_1=16,
            decoder_lstm_2=32,
            dropout_rate=0.2,
            learning_rate=1e-3,
            batch_size=32,
            epochs=50,
            validation_split=0.2,
            early_stopping_patience=5,
        )
    
    # Step 3: Train model
    print(f"\\n[3/7] Training LSTM autoencoder...")
    
    preprocessor = LSTMAutoencoderPreprocessor(windowing_config)
    service = LSTMAutoencoderService(preprocessor, model_config)
    
    train_result = service.fit(df_train, verbose=1)
    print(f"  Training windows: {train_result['n_train_windows']:,}")
    print(f"  Final train loss: {service.history_['loss'][-1]:.6f}")
    print(f"  Final val loss: {service.history_['val_loss'][-1]:.6f}")
    
    # Step 4: Save model
    print(f"\\n[4/7] Saving model artifacts...")
    model_artifacts_path = component_dir / "model"
    service.save(str(model_artifacts_path))
    print(f"  Saved to: {model_artifacts_path}")
    
    # Step 5: Run inference
    print(f"\\n[5/7] Running inference on test data...")
    pred_result = service.predict_windows(df_test, return_reconstruction=True)
    print(f"  Prediction windows: {pred_result['y_pred'].shape[0]:,}")
    
    # Step 6: Fit and compute Health Index
    print(f"\\n[6/7] Computing Health Index...")
    
    # Fit HI service on train reconstruction errors
    train_pred = service.predict_windows(df_train, return_reconstruction=True)
    
    hi_config = HealthIndexConfig(
        alpha=1.0,
        time_agg="mean",
        signal_agg="rms",
        unit_agg="mean",
        percentile_low=50,
        percentile_high=95,
    )
    
    hi_service = HealthIndexService(
        signal_cols=signal_cols,
        config=hi_config
    )
    
    hi_service.fit_error_stats(
        y_true=train_pred["y_true"],
        y_pred=train_pred["y_pred"]
    )
    
    # Score test windows
    signal_window_df, window_hi_df, unit_hi_df = hi_service.score_windows(
        y_true=pred_result["y_true"],
        y_pred=pred_result["y_pred"],
        pred_meta=pred_result["pred_meta"]
    )
    
    print(f"  Window HI shape: {window_hi_df.shape}")
    print(f"  Unit HI shape: {unit_hi_df.shape}")
    print(f"  Mean Health Index: {window_hi_df['health_index'].mean():.4f}")
    
    # Step 7: Save Health Index artifacts
    print(f"\\n[7/7] Saving Health Index artifacts...")
    hi_artifacts_path = component_dir / "health_index"
    hi_service.save(str(hi_artifacts_path))
    print(f"  Saved to: {hi_artifacts_path}")
    
    # Add component name to results
    window_hi_df["component"] = component_name
    unit_hi_df["component"] = component_name
    signal_window_df["component"] = component_name
    
    print(f"\\n✓ Component {component_name} processing complete!")
    
    return {
        "window_hi_df": window_hi_df,
        "unit_hi_df": unit_hi_df,
        "signal_window_df": signal_window_df,
        "model_artifacts_path": str(model_artifacts_path),
        "hi_artifacts_path": str(hi_artifacts_path),
        "train_history": service.history_,
    }"""
    })
    
    notebook_cells.append({
        "language": "markdown",
        "content": """### 11.3 Full Pipeline Orchestration"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """def run_full_pipeline(
    run_optimization: bool = False,
    n_trials: int = 20,
    components_to_process: Optional[List[str]] = None,
) -> Dict[str, Any]:
    \"\"\"
    Run the complete pipeline for all components defined in the mapping.
    
    Parameters:
    -----------
    run_optimization : Whether to run Optuna optimization for each component
    n_trials : Number of Optuna trials per component
    components_to_process : Optional list of specific components to process
    
    Returns:
    --------
    Dictionary containing:
    - all_window_hi: Consolidated window-level Health Index for all components
    - all_unit_hi: Consolidated unit-level Health Index for all components
    - component_results: Individual results per component
    \"\"\"
    print(f"\\n{'#'*80}")
    print(f"# STARTING FULL PIPELINE")
    print(f"{'#'*80}")
    
    # Determine which components to process
    all_components = set()
    for truck_model, components in model_components.items():
        all_components.update(components.keys())
    
    if components_to_process:
        components_to_run = [c for c in components_to_process if c in all_components]
    else:
        components_to_run = list(all_components)
    
    print(f"\\nComponents to process: {components_to_run}")
    print(f"Run optimization: {run_optimization}")
    print(f"Trials per component: {n_trials}")
    
    # Process each component
    component_results = {}
    all_window_hi = []
    all_unit_hi = []
    
    for component_name in components_to_run:
        # Get signals for this component from first model that has it
        signal_cols = None
        for truck_model, components in model_components.items():
            if component_name in components:
                signal_cols = components[component_name]["signals"]
                break
        
        if not signal_cols:
            print(f"\\n⚠ Skipping {component_name}: no signals defined")
            continue
        
        # Get units that have this component
        units_with_component = [
            unit_id for unit_id, truck_model in id_to_truck_model.items()
            if component_name in model_components.get(truck_model, {})
        ]
        
        if not units_with_component:
            print(f"\\n⚠ Skipping {component_name}: no units found")
            continue
        
        print(f"\\nUnits with {component_name}: {units_with_component}")
        
        # Filter data for these units
        df_train_comp = df_train_full[df_train_full[UNIT_COL].isin(units_with_component)].copy()
        df_test_comp = df_test_full[df_test_full[UNIT_COL].isin(units_with_component)].copy()
        
        if len(df_train_comp) == 0 or len(df_test_comp) == 0:
            print(f"\\n⚠ Skipping {component_name}: insufficient data")
            continue
        
        # Process component
        try:
            result = process_component(
                component_name=component_name,
                signal_cols=signal_cols,
                df_train=df_train_comp,
                df_test=df_test_comp,
                window_size=60,
                run_optimization=run_optimization,
                n_trials=n_trials,
                use_best_params=True,
            )
            
            component_results[component_name] = result
            all_window_hi.append(result["window_hi_df"])
            all_unit_hi.append(result["unit_hi_df"])
            
        except Exception as e:
            print(f"\\n✗ Error processing {component_name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Consolidate results
    print(f"\\n{'#'*80}")
    print(f"# CONSOLIDATING RESULTS")
    print(f"{'#'*80}")
    
    consolidated_window_hi = pd.concat(all_window_hi, ignore_index=True) if all_window_hi else pd.DataFrame()
    consolidated_unit_hi = pd.concat(all_unit_hi, ignore_index=True) if all_unit_hi else pd.DataFrame()
    
    # Add truck model to results
    if not consolidated_window_hi.empty:
        consolidated_window_hi["truck_model"] = consolidated_window_hi[UNIT_COL].map(id_to_truck_model)
    if not consolidated_unit_hi.empty:
        consolidated_unit_hi["truck_model"] = consolidated_unit_hi[UNIT_COL].map(id_to_truck_model)
    
    # Save consolidated results
    if not consolidated_window_hi.empty:
        consolidated_window_hi.to_parquet(HEALTH_INDEX_PATH, index=False)
        print(f"\\n✓ Saved consolidated Health Index to: {HEALTH_INDEX_PATH}")
        print(f"  Shape: {consolidated_window_hi.shape}")
    
    # Display summary
    print(f"\\n{'='*80}")
    print(f"PIPELINE SUMMARY")
    print(f"{'='*80}")
    print(f"Components processed: {len(component_results)}")
    print(f"Total windows: {len(consolidated_window_hi):,}")
    print(f"Total units: {consolidated_unit_hi[UNIT_COL].nunique() if not consolidated_unit_hi.empty else 0}")
    
    if not consolidated_unit_hi.empty:
        print(f"\\nHealth Index by component:")
        summary = consolidated_unit_hi.groupby("component")["health_index"].agg(["mean", "std", "min", "max", "count"])
        print(summary)
    
    return {
        "all_window_hi": consolidated_window_hi,
        "all_unit_hi": consolidated_unit_hi,
        "component_results": component_results,
    }"""
    })
    
    # ==================== SECTION 12: Example Execution ====================
    notebook_cells.append({
        "language": "markdown",
        "content": """## 12. Example: Run Full Pipeline

Uncomment and run the desired execution mode:

**Mode 1: Quick test (no optimization)**
```python
results = run_full_pipeline(
    run_optimization=False,
    components_to_process=["Motor"]  # Test with one component
)
```

**Mode 2: Full run with optimization**
```python
results = run_full_pipeline(
    run_optimization=True,
    n_trials=50
)
```

**Mode 3: Process specific components**
```python
results = run_full_pipeline(
    run_optimization=False,
    components_to_process=["Motor", "Frenos", "Direccion"]
)
```"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """# Example: Quick test with one component (no optimization)
# results = run_full_pipeline(
#     run_optimization=False,
#     n_trials=20,
#     components_to_process=["Motor"]
# )

# Uncomment to execute
print("Pipeline ready. Uncomment the execution mode above to run.")"""
    })
    
    # ==================== SECTION 13: Visualization ====================
    notebook_cells.append({
        "language": "markdown",
        "content": """## 13. Results Visualization

Visualize Health Index results after running the pipeline."""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """import matplotlib.pyplot as plt
import seaborn as sns

def visualize_health_index(results: Dict[str, Any]):
    \"\"\"Visualize Health Index results.\"\"\"
    window_hi_df = results["all_window_hi"]
    unit_hi_df = results["all_unit_hi"]
    
    if window_hi_df.empty:
        print("No results to visualize")
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. Health Index distribution by component
    sns.boxplot(data=window_hi_df, x="component", y="health_index", ax=axes[0, 0])
    axes[0, 0].set_title("Health Index Distribution by Component")
    axes[0, 0].set_xlabel("Component")
    axes[0, 0].set_ylabel("Health Index")
    axes[0, 0].grid(True, alpha=0.3)
    
    # 2. Health Index over time (if available)
    if "start_time" in window_hi_df.columns:
        for component in window_hi_df["component"].unique():
            comp_data = window_hi_df[window_hi_df["component"] == component]
            comp_agg = comp_data.groupby("start_time")["health_index"].mean().reset_index()
            axes[0, 1].plot(comp_agg["start_time"], comp_agg["health_index"], label=component, alpha=0.7)
        axes[0, 1].set_title("Health Index Over Time")
        axes[0, 1].set_xlabel("Time")
        axes[0, 1].set_ylabel("Mean Health Index")
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
    
    # 3. Reconstruction error by component
    sns.violinplot(data=window_hi_df, x="component", y="reconstruction_error_score", ax=axes[1, 0])
    axes[1, 0].set_title("Reconstruction Error Score by Component")
    axes[1, 0].set_xlabel("Component")
    axes[1, 0].set_ylabel("Reconstruction Error Score")
    axes[1, 0].grid(True, alpha=0.3)
    
    # 4. Unit-level Health Index
    if not unit_hi_df.empty:
        unit_hi_df_sorted = unit_hi_df.sort_values("health_index")
        sns.barplot(data=unit_hi_df_sorted, x=UNIT_COL, y="health_index", hue="component", ax=axes[1, 1])
        axes[1, 1].set_title("Health Index by Unit and Component")
        axes[1, 1].set_xlabel("Unit")
        axes[1, 1].set_ylabel("Health Index")
        axes[1, 1].legend(title="Component", bbox_to_anchor=(1.05, 1), loc='upper left')
        axes[1, 1].grid(True, alpha=0.3)
        plt.setp(axes[1, 1].xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    plt.show()

# Uncomment to visualize after running pipeline
# visualize_health_index(results)"""
    })
    
    # ==================== SECTION 14: Load Saved Results ====================
    notebook_cells.append({
        "language": "markdown",
        "content": """## 14. Load and Inspect Saved Results

Load previously saved Health Index results and model artifacts."""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """# Load saved Health Index
if HEALTH_INDEX_PATH.exists():
    consolidated_hi = pd.read_parquet(HEALTH_INDEX_PATH)
    print(f"Loaded Health Index: {consolidated_hi.shape}")
    print(f"\\nColumns: {consolidated_hi.columns.tolist()}")
    print(f"\\nComponents: {consolidated_hi['component'].unique().tolist()}")
    print(f"Units: {consolidated_hi[UNIT_COL].unique().tolist()}")
    print(f"\\nDate range: {consolidated_hi['start_time'].min()} to {consolidated_hi['end_time'].max()}")
    print(f"\\nHealth Index summary:")
    print(consolidated_hi.groupby("component")["health_index"].describe())
else:
    print(f"Health Index file not found: {HEALTH_INDEX_PATH}")"""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """# Example: Load a specific component's model
def load_component_model(component_name: str) -> LSTMAutoencoderService:
    \"\"\"Load a saved component model.\"\"\"
    model_path = CLIENT_MODELS_DIR / component_name / "model"
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    
    service = LSTMAutoencoderService.load(str(model_path))
    print(f"✓ Loaded {component_name} model from {model_path}")
    return service

# Example: Load Motor component
# motor_service = load_component_model("Motor")"""
    })
    
    # ==================== SECTION 15: Export and Summary ====================
    notebook_cells.append({
        "language": "markdown",
        "content": """## 15. Export Compact Health Index

Export the most compact representation: Unit, start_time, end_time, health_index, component."""
    })
    
    notebook_cells.append({
        "language": "python",
        "content": """def export_compact_health_index(
    window_hi_df: pd.DataFrame,
    output_path: Path
) -> pd.DataFrame:
    \"\"\"
    Export compact Health Index with essential columns only.
    
    Returns: DataFrame with columns:
    - Unit
    - start_time
    - end_time
    - health_index
    - component
    - truck_model (if available)
    - reconstruction_error_score (optional)
    \"\"\"
    essential_cols = [UNIT_COL, "start_time", "end_time", "health_index", "component"]
    optional_cols = ["truck_model", "reconstruction_error_score", "created_fraction", "imputed_fraction"]
    
    cols_to_keep = essential_cols + [c for c in optional_cols if c in window_hi_df.columns]
    
    compact_df = window_hi_df[cols_to_keep].copy()
    compact_df.to_parquet(output_path, index=False)
    
    print(f"✓ Exported compact Health Index to: {output_path}")
    print(f"  Shape: {compact_df.shape}")
    print(f"  Columns: {compact_df.columns.tolist()}")
    
    return compact_df

# Example usage (uncomment after running pipeline)
# compact_hi = export_compact_health_index(
#     results["all_window_hi"],
#     HEALTH_INDEX_PATH.parent / "health_index_compact.parquet"
# )"""
    })
    
    notebook_cells.append({
        "language": "markdown",
        "content": """## Summary

This notebook provides a complete, modular implementation of the Health Index pipeline:

### Key Features

1. **Service-oriented architecture** - Business logic encapsulated in reusable classes
2. **Mapping-driven execution** - Components, units, and signals configured via `full_mapping.json`
3. **Hyperparameter optimization** - Optuna integration with MLflow tracking
4. **Modular preprocessing** - Windowing, scaling, encoding handled by dedicated service
5. **LSTM autoencoder** - Seq2seq architecture for anomaly detection
6. **Health Index scoring** - Normalized reconstruction errors with configurable aggregation
7. **Artifact persistence** - Models, preprocessors, and HI configs saved for reuse
8. **Full orchestration** - End-to-end pipeline from raw data to consolidated HI table

### Output Artifacts

- **Processed Data**: `data/telemetry/silver/{client}/processed_data.parquet`
- **Health Index**: `data/telemetry/golden/{client}/health_index.parquet`
- **Models**: `models/{client}/{component}/model/`
- **Health Index Config**: `models/{client}/{component}/health_index/`
- **Optuna Studies**: `models/{client}/{component}/optuna_study.pkl`
- **MLflow Experiments**: `mlruns/`

### Next Steps

To convert this notebook into a Python package:

1. Extract service classes into `src/health_index/services/`
2. Extract configuration dataclasses into `src/health_index/config.py`
3. Create CLI interface using `click` or `typer`
4. Add unit tests for each service
5. Create setup.py for package distribution"""
    })
    
    # Generate the notebook XML
    notebook_cells_json = []
    
    for cell in notebook_cells:
        lang = cell["language"]
        content = cell["content"]
        
        if lang == "markdown":
            cell_json = {
                "cell_type": "markdown",
                "metadata": {},
                "source": [line + "\n" for line in content.split("\n")]
            }
        else:  # python
            cell_json = {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [line + "\n" for line in content.split("\n")]
            }
        
        notebook_cells_json.append(cell_json)
    
    # Create notebook structure
    notebook_json = {
        "cells": notebook_cells_json,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "codemirror_mode": {
                    "name": "ipython",
                    "version": 3
                },
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.10.0"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }
    
    return notebook_json


def main():
    """Main function to generate the notebook."""
    print("Generating health_index_modular.ipynb...")
    
    # Get the directory of this script
    script_dir = Path(__file__).parent
    output_path = script_dir / "notebooks" / "health_index_modular.ipynb"
    output_path.parent.mkdir(exist_ok=True)
    
    # Generate notebook content
    notebook_json = create_notebook()
    
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(notebook_json, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Successfully generated: {output_path}")
    print(f"  File size: {output_path.stat().st_size / 1024:.1f} KB")
    print(f"  Cells: {len(notebook_json['cells'])}")
    print("\nYou can now open this notebook in VS Code.")


if __name__ == "__main__":
    main()
