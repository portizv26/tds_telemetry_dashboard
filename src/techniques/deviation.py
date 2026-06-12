"""
Deviation Analysis — Threshold-based risk classification.

Computes percentile-based limits per model_specification/state/signal,
then classifies each telemetry minute into risk levels.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd
from tqdm import tqdm

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


def _classify_vectorized(values: np.ndarray, states: np.ndarray, thresholds: dict, risk_direction: str) -> np.ndarray:
    """Classify an entire array of values into risk levels using vectorized operations."""
    result = np.full(len(values), "unknown", dtype=object)

    for state, t in thresholds.items():
        state_mask = states == state
        if not state_mask.any():
            continue

        v = values[state_mask]
        valid = ~pd.isna(v)
        classified = np.full(state_mask.sum(), "unknown", dtype=object)

        if risk_direction == "high":
            classified[valid] = "normal"
            classified[valid & (v >= t["alert"][0])] = "alert"
            classified[valid & (v >= t["anormal"][0])] = "anormal"
            classified[valid & (v >= t["critical"][0])] = "critical"

        elif risk_direction == "low":
            classified[valid] = "normal"
            classified[valid & (v <= t["alert"][0])] = "alert"
            classified[valid & (v <= t["anormal"][0])] = "anormal"
            classified[valid & (v <= t["critical"][0])] = "critical"

        else:  # both
            classified[valid] = "normal"
            classified[valid & ((v <= t["alert"][0]) | (v >= t["alert"][1]))] = "alert"
            classified[valid & ((v <= t["anormal"][0]) | (v >= t["anormal"][1]))] = "anormal"
            classified[valid & ((v <= t["critical"][0]) | (v >= t["critical"][1]))] = "critical"

        result[state_mask] = classified

    return result


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

    # Pre-allocate risk level columns directly on a copy
    risk_col_names = []
    signals_to_process = [
        s for s in signal_registry["signals"]
        if s.get("threshold_compute", False)
    ]
    for signal_meta in signals_to_process:
        col_name = f"risk_level_{signal_meta['name']}"
        risk_col_names.append(col_name)

    # Initialize all risk columns as "unknown"
    out = df.copy()
    for col_name in risk_col_names:
        out[col_name] = "unknown"

    model_specs = [m for m in df["model_specification"].unique() if m in limits]
    total_steps = len(model_specs) * len(signals_to_process)

    with tqdm(total=total_steps, desc="Deviation analysis", unit="signal") as pbar:
        for model_spec in model_specs:
            model_mask = df["model_specification"] == model_spec
            model_idx = df.index[model_mask]
            states_arr = df.loc[model_mask, STATE_COLNAME].values

            for signal_meta in signals_to_process:
                feature = signal_meta["name"]
                if feature not in limits[model_spec]:
                    pbar.update(1)
                    continue
                if feature not in df.columns:
                    pbar.update(1)
                    continue

                risk_dir = signal_meta["risk_direction"]
                thresholds = _get_thresholds(limits[model_spec], feature, risk_dir)

                col_name = f"risk_level_{feature}"
                risk_levels = _classify_vectorized(
                    df.loc[model_mask, feature].values, states_arr, thresholds, risk_dir
                )

                out.loc[model_idx, col_name] = risk_levels
                pbar.update(1)

    out.set_index([UNIT_COLNAME, TIME_COLNAME], inplace=True)
    return out


def summarize_deviation(
    df_labeled: pd.DataFrame,
    signal_registry: dict,
    baseline_version: str,
) -> pd.DataFrame:
    """
    Summarize deviation results into per-unit, per-signal metrics.

    Returns:
        DataFrame with risk_score, confidence_score, status per (unit, signal).
    """
    risk_cols = [c for c in df_labeled.columns if c.startswith("risk_level_")]
    if not risk_cols:
        return pd.DataFrame()

    df_reset = df_labeled.reset_index()
    units = df_reset[UNIT_COLNAME].unique()

    # Build signal metadata lookup
    signal_meta_map = {s["name"]: s for s in signal_registry["signals"]}

    records = []

    for col in tqdm(risk_cols, desc="Summarizing deviation", unit="signal"):
        feature = col.replace("risk_level_", "")
        meta = signal_meta_map.get(feature)
        if not meta:
            continue

        # Filter out unknowns once for the whole column
        valid_mask = df_reset[col] != "unknown"
        valid_df = df_reset.loc[valid_mask, [UNIT_COLNAME, col]]

        if valid_df.empty:
            continue

        # Vectorized counts per unit using groupby + value_counts
        grouped = valid_df.groupby(UNIT_COLNAME)[col].value_counts().unstack(fill_value=0)

        for unit in units:
            if unit not in grouped.index:
                continue

            counts = grouped.loc[unit]
            total = int(counts.sum())
            if total == 0:
                continue

            alert_count = int(counts.get("alert", 0))
            anormal_count = int(counts.get("anormal", 0))
            critical_count = int(counts.get("critical", 0))

            abnormal_pct = (anormal_count + critical_count) / total * 100
            alert_pct = alert_count / total * 100
            critical_pct = critical_count / total * 100

            risk_score = min(abnormal_pct * 6, 100)
            if critical_pct > 0:
                risk_score = min(risk_score * 1.3, 100)

            confidence = calculate_confidence(
                valid_samples=total,
                expected_samples=1440,
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
