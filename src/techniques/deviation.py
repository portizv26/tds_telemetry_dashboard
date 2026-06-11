"""
Deviation Analysis — Threshold-based risk classification.

Computes percentile-based limits per model_specification/state/signal,
then classifies each telemetry minute into risk levels.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

from src.config.settings import (
    UNIT_COLNAME,
    STATE_COLNAME,
    TIME_COLNAME,
    DeviationConfig,
)
from src.utils.data_utils import (
    get_features_for_computation,
    classify_status,
    calculate_confidence,
)

logger = logging.getLogger(__name__)


def compute_limits(
    df: pd.DataFrame,
    signal_registry: dict,
    config: DeviationConfig,
) -> dict:
    """
    Compute percentile-based limits per model_specification/state/signal.

    Parameters:
        df: DataFrame with model_specification column
        signal_registry: Signal registry dict
        config: Deviation analysis configuration

    Returns:
        Nested dict: {model_spec: {signal: {state: {P1..P99}}}}
    """
    limits = {}
    features = get_features_for_computation(signal_registry)

    valid_pairs = (
        df[["model_specification", STATE_COLNAME]]
        .drop_duplicates()
        .dropna(how="any")
    )
    valid_pairs = [
        (row["model_specification"], row[STATE_COLNAME])
        for _, row in valid_pairs.iterrows()
        if pd.notna(row["model_specification"]) and pd.notna(row[STATE_COLNAME])
    ]

    for model_spec, state in valid_pairs:
        if model_spec not in limits:
            limits[model_spec] = {}

        mask = (df["model_specification"] == model_spec) & (df[STATE_COLNAME] == state)
        subset = df.loc[mask]

        for feature in features:
            if feature not in subset.columns:
                continue

            values = subset[feature].dropna()
            if values.nunique() < config.min_unique_values:
                continue

            if feature not in limits[model_spec]:
                limits[model_spec][feature] = {}

            p = np.percentile(values, config.percentiles)
            limits[model_spec][feature][state] = {
                f"P{pct}": round(float(val), 2)
                for pct, val in zip(config.percentiles, p)
            }
            limits[model_spec][feature][state]["sample_count"] = int(len(values))

    logger.info(
        f"Computed limits: {len(limits)} models, "
        f"{sum(len(v) for v in limits.values())} model-signal combinations"
    )
    return limits


def limits_to_dataframe(limits: dict, computation_date: datetime) -> pd.DataFrame:
    """
    Convert the nested limits dict into a flat DataFrame for persistence.

    Parameters:
        limits: Nested dict {model_spec: {signal: {state: {P1..P99, sample_count}}}}
        computation_date: Date when limits were computed

    Returns:
        DataFrame with one row per (model_specification, signal, state).
    """
    records = []
    for model_spec, signals in limits.items():
        for signal, states in signals.items():
            for state, percentiles in states.items():
                record = {
                    "model_specification": model_spec,
                    "signal": signal,
                    "state": state,
                    "computation_date": computation_date.date(),
                }
                for key, val in percentiles.items():
                    if key != "sample_count":
                        record[key] = val
                record["sample_count"] = percentiles.get("sample_count", 0)
                records.append(record)

    return pd.DataFrame(records)


def persist_limits(limits: dict, limits_path, computation_date: datetime) -> None:
    """
    Persist computed limits to the Silver layer as a parquet file.

    Parameters:
        limits: Nested dict from compute_limits()
        limits_path: Path to the limits directory
        computation_date: Date for file naming
    """
    from pathlib import Path
    limits_path = Path(limits_path)
    limits_path.mkdir(parents=True, exist_ok=True)

    df = limits_to_dataframe(limits, computation_date)
    if df.empty:
        logger.warning("No limits to persist (empty DataFrame)")
        return

    filename = f"limits_{computation_date.strftime('%Y%m%d')}.parquet"
    filepath = limits_path / filename
    df.to_parquet(filepath, index=False)
    logger.info(f"Persisted {len(df)} limit records to {filepath}")


def _get_thresholds(limits_model: dict, feature: str, risk_direction: str) -> dict:
    """Extract alert/anormal/critical thresholds per state for a feature."""
    if feature not in limits_model:
        return {}

    result = {}
    for state, percs in limits_model[feature].items():
        if risk_direction == "high":
            result[state] = {
                "alert": [percs["P95"]],
                "anormal": [percs["P98"]],
                "critical": [percs["P99"]],
            }
        elif risk_direction == "low":
            result[state] = {
                "alert": [percs["P5"]],
                "anormal": [percs["P2"]],
                "critical": [percs["P1"]],
            }
        else:  # both
            result[state] = {
                "alert": [percs["P5"], percs["P95"]],
                "anormal": [percs["P2"], percs["P98"]],
                "critical": [percs["P1"], percs["P99"]],
            }
    return result


def _classify_value(value: float, state: str, thresholds: dict, risk_direction: str) -> str:
    """Classify a single value into a risk level."""
    if pd.isna(value) or state not in thresholds:
        return "unknown"

    t = thresholds[state]

    if risk_direction == "high":
        if value < t["alert"][0]:
            return "normal"
        elif value < t["anormal"][0]:
            return "alert"
        elif value < t["critical"][0]:
            return "anormal"
        return "critical"

    elif risk_direction == "low":
        if value > t["alert"][0]:
            return "normal"
        elif value > t["anormal"][0]:
            return "alert"
        elif value > t["critical"][0]:
            return "anormal"
        return "critical"

    else:  # both
        if value <= t["critical"][0] or value >= t["critical"][1]:
            return "critical"
        elif value <= t["anormal"][0] or value >= t["anormal"][1]:
            return "anormal"
        elif value <= t["alert"][0] or value >= t["alert"][1]:
            return "alert"
        return "normal"


def apply_deviation_analysis(
    df: pd.DataFrame,
    limits: dict,
    signal_registry: dict,
) -> pd.DataFrame:
    """
    Apply threshold comparison to all signals, producing risk_level columns.

    Parameters:
        df: DataFrame with model_specification, Estado, and signal columns
        limits: Pre-computed limits dict
        signal_registry: Signal metadata

    Returns:
        DataFrame with risk_level_{signal} columns added, indexed by (Unit, Fecha).
    """
    features = get_features_for_computation(signal_registry)
    result_frames = []

    for model_spec in df["model_specification"].unique():
        if model_spec not in limits:
            continue

        model_mask = df["model_specification"] == model_spec
        model_df = df.loc[model_mask]

        for signal_meta in signal_registry["signals"]:
            feature = signal_meta["name"]
            if not signal_meta.get("threshold_compute", False):
                continue
            if feature not in limits[model_spec]:
                continue
            if feature not in model_df.columns:
                continue

            risk_dir = signal_meta["risk_direction"]
            thresholds = _get_thresholds(limits[model_spec], feature, risk_dir)

            col_name = f"risk_level_{feature}"
            # Vectorized classification using numpy
            risk_levels = np.array([
                _classify_value(v, s, thresholds, risk_dir)
                for v, s in zip(model_df[feature].values, model_df[STATE_COLNAME].values)
            ])

            label_df = pd.DataFrame(
                {col_name: risk_levels},
                index=model_df.index,
            )
            result_frames.append(label_df)

    if not result_frames:
        logger.warning("No deviation results produced")
        return df.set_index([UNIT_COLNAME, TIME_COLNAME])

    labels = pd.concat(result_frames, axis=1)
    # Group duplicate columns (same signal from different models)
    labels = labels.T.groupby(level=0).first().T

    out = pd.concat([df, labels], axis=1)
    out.set_index([UNIT_COLNAME, TIME_COLNAME], inplace=True)
    return out


def summarize_deviation(
    df_labeled: pd.DataFrame,
    signal_registry: dict,
    baseline_version: str,
) -> pd.DataFrame:
    """
    Summarize deviation results into per-unit, per-signal, per-day metrics.

    Returns:
        DataFrame with risk_score, confidence_score, status per (unit, signal, date).
    """
    risk_cols = [c for c in df_labeled.columns if c.startswith("risk_level_")]
    if not risk_cols:
        return pd.DataFrame()

    records = []
    df_reset = df_labeled.reset_index()

    for unit in df_reset[UNIT_COLNAME].unique():
        unit_df = df_reset[df_reset[UNIT_COLNAME] == unit]

        for col in risk_cols:
            feature = col.replace("risk_level_", "")
            meta = next((s for s in signal_registry["signals"] if s["name"] == feature), None)
            if not meta:
                continue

            valid_mask = unit_df[col] != "unknown"
            valid = unit_df.loc[valid_mask, col]

            if len(valid) == 0:
                continue

            total = len(valid)
            abnormal_pct = ((valid == "anormal").sum() + (valid == "critical").sum()) / total * 100
            alert_pct = (valid == "alert").sum() / total * 100
            critical_pct = (valid == "critical").sum() / total * 100

            # Risk score: 10% abnormal → 60
            risk_score = min(abnormal_pct * 6, 100)
            if critical_pct > 0:
                risk_score = min(risk_score * 1.3, 100)

            confidence = calculate_confidence(
                valid_samples=total,
                expected_samples=1440,  # 24h of minutes
                baseline_sample_count=1000,
            )

            records.append({
                "unit": unit,
                "signal": feature,
                "system": meta.get("system", "unknown"),
                "risk_score": round(risk_score, 1),
                "confidence_score": round(confidence, 1),
                "status": classify_status(risk_score, confidence),
                "abnormal_pct": round(abnormal_pct, 2),
                "alert_pct": round(alert_pct, 2),
                "critical_pct": round(critical_pct, 2),
                "total_minutes_evaluated": total,
                "baseline_version": baseline_version,
                "execution_timestamp": datetime.utcnow(),
            })

    return pd.DataFrame(records)
