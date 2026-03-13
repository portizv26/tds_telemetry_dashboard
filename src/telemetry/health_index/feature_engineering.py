"""
Feature engineering module.

Single responsibility: transform clean DataFrames into numpy arrays
(sequences / inference windows) suitable for the LSTM autoencoder.
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder, RobustScaler

from src.utils.logger import get_logger

from .config import HealthIndexConfig

logger = get_logger(__name__)


# ── Encoder fitting ─────────────────────────────────────────────────────────


def fit_encoders(
    df: pd.DataFrame,
    num_cols: List[str],
    cat_cols: List[str],
    unit_col: str,
) -> Tuple[Dict[str, RobustScaler], OneHotEncoder]:
    """
    Fit one ``RobustScaler`` per unit and one shared ``OneHotEncoder``.

    Both are fitted on ``.values`` (numpy) to avoid feature-name warnings
    when transforming later.
    """
    scalers: Dict[str, RobustScaler] = {}
    for unit in df[unit_col].unique():
        sc = RobustScaler()
        sc.fit(df.loc[df[unit_col] == unit, num_cols].values)
        scalers[unit] = sc

    ohe = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    ohe.fit(df[cat_cols].values)
    return scalers, ohe


# ── Sequence building (for training) ────────────────────────────────────────


def build_sequences(
    df: pd.DataFrame,
    signal_cols: List[str],
    cat_cols: List[str],
    scalers: Dict[str, RobustScaler],
    ohe: OneHotEncoder,
    cfg: HealthIndexConfig,
    label_filter: Optional[str] = "Normal",
) -> np.ndarray:
    """
    Create sliding-window sequences ``[n_sequences, window_size, n_features]``.

    Numerical columns are scaled per-unit; categorical columns are OHE.
    If *label_filter* is given only rows with that label are used.
    """
    subset = df[df["Label"] == label_filter] if label_filter else df
    # hard filling within each cycle
    subset = subset.sort_values([cfg.unit_col, "cycle_id", cfg.time_col])
    subset[signal_cols] = (
        subset.groupby([cfg.unit_col, "cycle_id"])[signal_cols].ffill().bfill()
    )

    sequences = []
    for unit in subset[cfg.unit_col].unique():
        unit_df = subset[subset[cfg.unit_col] == unit]
        sc = scalers[unit]
        for cycle in unit_df["cycle_id"].unique():
            cdf = unit_df[unit_df["cycle_id"] == cycle]
            if len(cdf) < cfg.window_size * 2:
                continue
            num_scaled = sc.transform(cdf[signal_cols].values)
            cat_encoded = ohe.transform(cdf[cat_cols].values)
            combined = np.hstack([num_scaled, cat_encoded])
            for i in range(len(combined) - cfg.window_size):
                sequences.append(combined[i : i + cfg.window_size])

    arr = np.array(sequences, dtype="float32")
    logger.info(f"Built {arr.shape[0]} sequences  shape={arr.shape}")
    return arr


# ── Inference window preparation ────────────────────────────────────────────


def prepare_inference_window(
    window_df: pd.DataFrame,
    signal_cols: List[str],
    cat_cols: List[str],
    scaler: RobustScaler,
    ohe: OneHotEncoder,
    window_size: int,
    num_fill: float = -10.0,
) -> Tuple[np.ndarray, float]:
    """
    Prepare a single window (1 unit, up to *window_size* rows) for the model.

    Edge cases:
      * Empty window (0 rows):  all filled with unlikely values.
      * Partial window (<window_size): real rows scaled; rest padded.

    Returns ``(X, coverage)`` where
    ``X.shape == (1, window_size, n_features)``.
    """
    n_num = len(signal_cols)
    n_cat = len(ohe.get_feature_names_out())
    n_features = n_num + n_cat
    actual_len = len(window_df)
    coverage = actual_len / window_size

    pad_row = np.concatenate([
        np.full(n_num, num_fill, dtype="float32"),
        np.zeros(n_cat, dtype="float32"),
    ])

    if actual_len == 0:
        X = np.tile(pad_row, (window_size, 1))[np.newaxis, :, :]
        return X, 0.0

    num_scaled = scaler.transform(window_df[signal_cols].values)
    cat_encoded = ohe.transform(window_df[cat_cols].values)
    combined = np.hstack([num_scaled, cat_encoded]).astype("float32")

    if actual_len < window_size:
        pad = np.tile(pad_row, (window_size - actual_len, 1))
        combined = np.vstack([combined, pad])

    return combined[np.newaxis, :window_size, :], coverage
