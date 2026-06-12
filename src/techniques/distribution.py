"""
Distribution Shift Analysis — Mann-Whitney U test for distribution changes.

Compares recent observation windows against historical baseline distributions,
controlling per operational state to detect significant behavioral shifts.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd
from tqdm import tqdm
from scipy.stats import mannwhitneyu

from src.config.settings import (
    UNIT_COLNAME,
    STATE_COLNAME,
    TIME_COLNAME,
    DistributionConfig,
)
from src.utils.data_utils import (
    get_features_for_computation,
    get_signal_metadata,
    classify_status,
    calculate_confidence,
)

logger = logging.getLogger(__name__)


def _cohens_d(baseline: np.ndarray, observation: np.ndarray) -> float:
    """Calculate Cohen's d effect size."""
    n1, n2 = len(baseline), len(observation)
    if n1 < 2 or n2 < 2:
        return 0.0
    pooled_std = np.sqrt(
        ((n1 - 1) * baseline.std() ** 2 + (n2 - 1) * observation.std() ** 2)
        / (n1 + n2 - 2)
    )
    if pooled_std == 0:
        return 0.0
    return float((observation.mean() - baseline.mean()) / pooled_std)


def _analyze_single_shift(
    unit_state_data: pd.DataFrame,
    feature: str,
    observation_weeks: int,
    baseline_weeks: int,
    min_baseline: int,
    min_observation: int,
) -> dict | None:
    """
    Run Mann-Whitney U test comparing recent vs historical data for one combination.

    Returns:
        Result dict or None if insufficient data.
    """
    if feature not in unit_state_data.columns:
        return None

    if not isinstance(unit_state_data.index, pd.DatetimeIndex):
        return None

    max_time = unit_state_data.index.max()
    observation_start = max_time - pd.Timedelta(weeks=observation_weeks)
    baseline_end = observation_start
    baseline_start = max_time - pd.Timedelta(weeks=baseline_weeks)

    observation_data = unit_state_data.loc[
        (unit_state_data.index >= observation_start) & (unit_state_data.index <= max_time),
        feature,
    ].dropna()

    baseline_data = unit_state_data.loc[
        (unit_state_data.index >= baseline_start) & (unit_state_data.index < baseline_end),
        feature,
    ].dropna()

    if len(observation_data) < min_observation or len(baseline_data) < min_baseline:
        return None

    try:
        u_stat, p_value = mannwhitneyu(
            baseline_data.values, observation_data.values, alternative="two-sided"
        )
    except Exception:
        return None

    effect = _cohens_d(baseline_data.values, observation_data.values)
    baseline_median = float(baseline_data.median())
    obs_median = float(observation_data.median())
    median_diff = obs_median - baseline_median
    median_pct = (median_diff / baseline_median * 100) if baseline_median != 0 else 0.0

    # Effect size category
    abs_d = abs(effect)
    if abs_d > 0.8:
        category = "large"
    elif abs_d > 0.5:
        category = "medium"
    elif abs_d > 0.2:
        category = "small"
    else:
        category = "negligible"

    return {
        "observation_weeks": observation_weeks,
        "p_value": float(p_value),
        "cohens_d": round(effect, 4),
        "effect_size_category": category,
        "is_significant": p_value < 0.05,
        "baseline_median": round(baseline_median, 3),
        "observation_median": round(obs_median, 3),
        "median_diff": round(median_diff, 3),
        "median_pct_change": round(median_pct, 2),
        "baseline_n": len(baseline_data),
        "observation_n": len(observation_data),
    }


def run_distribution_analysis(
    df: pd.DataFrame,
    signal_registry: dict,
    config: DistributionConfig,
    baseline_version: str = "",
) -> pd.DataFrame:
    """
    Run distribution shift analysis across all units, features, states, and windows.

    Parameters:
        df: Raw telemetry DataFrame
        signal_registry: Signal metadata
        config: Distribution analysis configuration
        baseline_version: Version for traceability

    Returns:
        DataFrame with shift analysis results.
    """
    features = get_features_for_computation(signal_registry)

    # Prepare indexed data
    if TIME_COLNAME in df.columns:
        work_df = df.set_index([UNIT_COLNAME, TIME_COLNAME])
    elif isinstance(df.index, pd.MultiIndex):
        work_df = df
    else:
        return pd.DataFrame()

    units = work_df.index.get_level_values(0).unique()
    states = work_df[STATE_COLNAME].dropna().unique() if STATE_COLNAME in work_df.columns else []

    records = []

    for unit in tqdm(units, desc="Distribution analysis", unit="unit"):
        try:
            unit_data = work_df.loc[unit]
        except KeyError:
            continue

        if not isinstance(unit_data.index, pd.DatetimeIndex):
            continue

        if STATE_COLNAME not in unit_data.columns:
            continue

        for state in states:
            state_data = unit_data[unit_data[STATE_COLNAME] == state]
            if len(state_data) < config.min_observation_samples:
                continue

            for feature in features:
                meta = get_signal_metadata(signal_registry, feature)
                if not meta:
                    continue

                for obs_weeks in config.observation_weeks:
                    result = _analyze_single_shift(
                        state_data,
                        feature,
                        obs_weeks,
                        config.baseline_weeks,
                        config.min_baseline_samples,
                        config.min_observation_samples,
                    )
                    if result is None:
                        continue

                    # Interpret shift direction
                    risk_dir = meta.get("risk_direction", "unknown")
                    median_diff = result["median_diff"]

                    if risk_dir == "high" and median_diff > 0:
                        interpretation = "worsening"
                    elif risk_dir == "low" and median_diff < 0:
                        interpretation = "worsening"
                    elif risk_dir == "both" and abs(median_diff) > 0:
                        interpretation = "drifting"
                    else:
                        interpretation = "improving"

                    # Risk score based on significance and effect size
                    if result["is_significant"] and interpretation == "worsening":
                        effect_score = {"large": 70, "medium": 50, "small": 30, "negligible": 10}
                        risk_score = effect_score.get(result["effect_size_category"], 10)
                    else:
                        risk_score = 0.0

                    confidence = calculate_confidence(
                        valid_samples=result["observation_n"],
                        expected_samples=obs_weeks * 7 * 24 * 60,
                        baseline_sample_count=result["baseline_n"],
                    )

                    records.append({
                        "unit": unit,
                        "signal": feature,
                        "system": meta.get("system", "unknown"),
                        "state": state,
                        "observation_weeks": obs_weeks,
                        "p_value": result["p_value"],
                        "cohens_d": result["cohens_d"],
                        "effect_size_category": result["effect_size_category"],
                        "is_significant": result["is_significant"],
                        "baseline_median": result["baseline_median"],
                        "observation_median": result["observation_median"],
                        "median_pct_change": result["median_pct_change"],
                        "shift_interpretation": interpretation,
                        "risk_score": round(risk_score, 1),
                        "confidence_score": round(confidence, 1),
                        "status": classify_status(risk_score, confidence),
                        "baseline_n": result["baseline_n"],
                        "observation_n": result["observation_n"],
                        "baseline_version": baseline_version,
                        "execution_timestamp": datetime.utcnow(),
                    })

    result_df = pd.DataFrame(records)
    logger.info(
        f"Distribution analysis complete: {len(result_df)} results, "
        f"{(result_df['is_significant']).sum() if len(result_df) > 0 else 0} significant"
    )
    return result_df
