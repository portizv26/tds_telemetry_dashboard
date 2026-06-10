"""
Trend Analysis — Linear regression over rolling-mean smoothed signals.

Detects statistically significant progressive degradation or improvement
over 4, 8, and 12-week time windows.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LinearRegression

from src.config.settings import (
    UNIT_COLNAME,
    STATE_COLNAME,
    TIME_COLNAME,
    TrendConfig,
)
from src.utils.data_utils import (
    get_features_for_computation,
    get_signal_metadata,
    classify_status,
    calculate_confidence,
)

logger = logging.getLogger(__name__)


def _analyze_single_trend(
    unit_data: pd.DataFrame,
    feature: str,
    window_weeks: int,
    rolling_window: int,
) -> dict | None:
    """
    Fit linear regression on rolling-mean smoothed signal for one unit/feature/window.

    Returns:
        Result dict or None if insufficient data.
    """
    if feature not in unit_data.columns:
        return None

    # Ensure datetime index
    if not isinstance(unit_data.index, pd.DatetimeIndex):
        return None

    max_time = unit_data.index.max()
    min_time = max_time - pd.Timedelta(weeks=window_weeks)
    window_data = unit_data.loc[unit_data.index >= min_time, feature].dropna()

    if len(window_data) < rolling_window * 2:
        return None

    smoothed = window_data.rolling(window=rolling_window, min_periods=1).mean().dropna()
    if len(smoothed) < 10:
        return None

    # Convert to numeric hours since start
    hours = (smoothed.index - smoothed.index[0]).total_seconds() / 3600
    X = hours.values.reshape(-1, 1)
    y = smoothed.values

    model = LinearRegression()
    model.fit(X, y)

    y_pred = model.predict(X)
    slope = model.coef_[0]
    r2 = model.score(X, y)
    n = len(X)

    # P-value for slope
    residuals = y - y_pred
    mse = np.sum(residuals**2) / max(n - 2, 1)
    x_var = np.sum((X.ravel() - X.mean()) ** 2)
    se_slope = np.sqrt(mse / max(x_var, 1e-10))
    t_stat = slope / max(se_slope, 1e-10)
    p_value = float(2 * (1 - stats.t.cdf(abs(t_stat), max(n - 2, 1))))

    return {
        "window_weeks": window_weeks,
        "slope_per_day": slope * 24,
        "r2": r2,
        "p_value": p_value,
        "is_significant": p_value < 0.05,
        "is_good_fit": r2 > 0.3,
        "data_points": n,
        "start_time": smoothed.index.min(),
        "end_time": smoothed.index.max(),
    }


def run_trend_analysis(
    df: pd.DataFrame,
    signal_registry: dict,
    config: TrendConfig,
    baseline_version: str = "",
) -> pd.DataFrame:
    """
    Run trend analysis across all units, features, and time windows.

    Parameters:
        df: Raw telemetry DataFrame (with Fecha as column or index)
        signal_registry: Signal metadata
        config: Trend configuration
        baseline_version: Version string for traceability

    Returns:
        DataFrame with trend results for all unit/signal/window combinations.
    """
    features = get_features_for_computation(signal_registry)

    # Prepare data: index by (Unit, Fecha)
    if TIME_COLNAME in df.columns:
        work_df = df.set_index([UNIT_COLNAME, TIME_COLNAME])
    elif isinstance(df.index, pd.MultiIndex):
        work_df = df
    else:
        logger.error("Cannot determine time index")
        return pd.DataFrame()

    units = work_df.index.get_level_values(0).unique()
    records = []

    for unit in units:
        try:
            unit_data = work_df.loc[unit]
        except KeyError:
            continue

        if not isinstance(unit_data.index, pd.DatetimeIndex):
            continue

        for feature in features:
            meta = get_signal_metadata(signal_registry, feature)
            if not meta:
                continue

            for window_weeks in config.window_weeks:
                result = _analyze_single_trend(
                    unit_data, feature, window_weeks, config.rolling_window_minutes
                )
                if result is None:
                    continue

                # Interpret trend direction
                risk_dir = meta.get("risk_direction", "unknown")
                slope = result["slope_per_day"]

                if risk_dir == "high" and slope > 0:
                    interpretation = "worsening"
                elif risk_dir == "low" and slope < 0:
                    interpretation = "worsening"
                elif risk_dir == "both" and abs(slope) > 0:
                    interpretation = "drifting"
                else:
                    interpretation = "improving"

                # Risk score
                if result["is_significant"] and result["is_good_fit"] and interpretation == "worsening":
                    magnitude = min(abs(slope) * 2, 50)
                    persistence = min(result["r2"] * 50, 30)
                    significance = 20 if result["p_value"] < 0.01 else 0
                    risk_score = min(magnitude + persistence + significance, 100)
                else:
                    risk_score = 0.0

                confidence = calculate_confidence(
                    valid_samples=result["data_points"],
                    expected_samples=window_weeks * 7 * 24 * 60,
                )

                records.append({
                    "unit": unit,
                    "signal": feature,
                    "system": meta.get("system", "unknown"),
                    "window_weeks": window_weeks,
                    "slope_per_day": round(slope, 6),
                    "r2": round(result["r2"], 4),
                    "p_value": round(result["p_value"], 6),
                    "is_significant": result["is_significant"],
                    "is_good_fit": result["is_good_fit"],
                    "risk_direction": risk_dir,
                    "trend_interpretation": interpretation,
                    "risk_score": round(risk_score, 1),
                    "confidence_score": round(confidence, 1),
                    "status": classify_status(risk_score, confidence),
                    "data_points": result["data_points"],
                    "start_time": result["start_time"],
                    "end_time": result["end_time"],
                    "baseline_version": baseline_version,
                    "execution_timestamp": datetime.utcnow(),
                })

    result_df = pd.DataFrame(records)
    logger.info(
        f"Trend analysis complete: {len(result_df)} results, "
        f"{(result_df['status'] == 'Anormal').sum() if len(result_df) > 0 else 0} Anormal"
    )
    return result_df
