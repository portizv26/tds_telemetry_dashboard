"""
Inference module.

Single responsibility: run prediction on prepared data windows and
produce reconstruction-error DataFrames.
"""

from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder, RobustScaler
from tensorflow.keras import Model
from tqdm.auto import tqdm

from src.utils.logger import get_logger

from .config import HealthIndexConfig
from .feature_engineering import prepare_inference_window

logger = get_logger(__name__)


def predict_window(
    window_df: pd.DataFrame,
    model: Model,
    scaler: RobustScaler,
    ohe: OneHotEncoder,
    signal_cols: List[str],
    cat_cols: List[str],
    window_size: int,
    num_fill: float = -10.0,
) -> dict:
    """
    Run inference on a single window for one unit.

    Returns ``{"reconstruction_error": float, "coverage": float}``.
    """
    X, coverage = prepare_inference_window(
        window_df, signal_cols, cat_cols, scaler, ohe, window_size, num_fill,
    )
    X_pred = model.predict(X, verbose=0)
    mse = float(np.mean((X - X_pred) ** 2))
    return {"reconstruction_error": mse, "coverage": coverage}


def run_hourly_inference(
    df: pd.DataFrame,
    artifacts: dict,
    cfg: HealthIndexConfig,
) -> pd.DataFrame:
    """
    Split the test data into aligned 1-hour windows per unit and apply
    the model to each window.

    Returns a DataFrame with one row per (unit, hour-window):
    ``Unit, window_start, window_end, reconstruction_error, coverage``.
    """
    model: Model = artifacts["model"]
    scalers: Dict[str, RobustScaler] = artifacts["scalers"]
    ohe: OneHotEncoder = artifacts["ohe"]
    meta: dict = artifacts["metadata"]
    signal_cols: List[str] = meta["signal_cols"]
    cat_cols: List[str] = meta["cat_cols"]
    window_size: int = meta["window_size"]

    records = []
    for unit in tqdm(df[cfg.unit_col].unique(), desc="Predicting"):
        scaler = scalers.get(unit)
        if scaler is None:
            continue
        udf = df[df[cfg.unit_col] == unit].sort_values(cfg.time_col)

        t_min = udf[cfg.time_col].min().floor("h")
        t_max = udf[cfg.time_col].max().ceil("h")
        hourly_starts = pd.date_range(t_min, t_max, freq="1h")

        for h_start in hourly_starts:
            h_end = h_start + pd.Timedelta(minutes=window_size)
            window_df = udf[
                (udf[cfg.time_col] >= h_start) & (udf[cfg.time_col] < h_end)
            ]
            result = predict_window(
                window_df, model, scaler, ohe,
                signal_cols, cat_cols, window_size,
                num_fill=cfg.impute_fill_value,
            )
            records.append({
                cfg.unit_col: unit,
                "window_start": h_start,
                "window_end": h_end,
                **result,
            })

    result_df = pd.DataFrame(records)
    logger.info(f"Inference windows: {len(result_df)}")
    return result_df
