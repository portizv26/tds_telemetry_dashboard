"""
Aggregation — Multi-level health assessment (Signal → System → Unit).

Combines technique results into system-level and unit-level health scores
with time-decay weighting, criticality-based prioritization, and multi-technique
agreement detection.
"""

import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from src.config.settings import AggregationConfig

logger = logging.getLogger(__name__)


def aggregate_system_health(
    technique_results: pd.DataFrame,
    signal_registry: dict,
    system_name: str,
    unit: str,
    config: AggregationConfig,
    evaluation_timestamp: datetime = None,
) -> dict:
    """
    Aggregate technique results into system-level health assessment.

    Parameters:
        technique_results: DataFrame with columns [unit, signal, system, technique,
                           risk_score, confidence_score, status, execution_timestamp]
        signal_registry: Signal metadata with criticality
        system_name: System to aggregate
        unit: Unit identifier
        config: Aggregation configuration
        evaluation_timestamp: Current time for decay calculation

    Returns:
        System health assessment dict.
    """
    if evaluation_timestamp is None:
        evaluation_timestamp = datetime.utcnow()

    # Filter for this unit and system
    mask = (technique_results["unit"] == unit) & (technique_results["system"] == system_name)
    results = technique_results.loc[mask].copy()

    if results.empty:
        return {
            "unit": unit,
            "system": system_name,
            "system_score": 0.0,
            "system_status": "InsufficientData",
            "confidence": 0.0,
            "n_techniques_triggered": 0,
            "top_signal": None,
            "top_signal_score": 0.0,
            "top_technique": None,
            "evaluation_timestamp": evaluation_timestamp,
        }

    # Get signal criticality map
    criticality_map = {}
    for s in signal_registry["signals"]:
        criticality_map[s["name"]] = s.get("criticality", 2)

    # Calculate weighted scores
    scores = []
    for _, row in results.iterrows():
        crit = criticality_map.get(row.get("signal", ""), 2)
        weight = 4 - crit  # criticality 1 → weight 3, criticality 3 → weight 1
        scores.append(row["risk_score"] * weight)

    # Key aggregation metrics
    max_critical_score = results["risk_score"].max()
    weighted_mean = np.mean(scores) if scores else 0.0

    # Multi-technique persistence bonus: multiple techniques flagging same signal
    triggered = results[results["status"].isin(["Alerta", "Anormal"])]
    signals_multi = triggered.groupby("signal").size()
    persistence_bonus = min(float(signals_multi.gt(1).sum()) * 15, 40)

    # Aggregate formula
    system_score = min(
        config.weight_max_critical * max_critical_score
        + config.weight_mean * weighted_mean
        + config.weight_persistence * persistence_bonus
        + config.weight_trend * 0,  # Trend penalty applied separately
        100.0,
    )

    # Classify
    n_triggered = len(triggered)
    if system_score >= config.alerta_max or (triggered["status"] == "Anormal").any():
        system_status = "Anormal"
    elif system_score >= config.normal_max or n_triggered > 0:
        system_status = "Alerta"
    else:
        system_status = "Normal"

    # Top evidence
    top_row = results.loc[results["risk_score"].idxmax()]

    return {
        "unit": unit,
        "system": system_name,
        "system_score": round(system_score, 1),
        "system_status": system_status,
        "confidence": round(float(results["confidence_score"].mean()), 1),
        "n_techniques_triggered": n_triggered,
        "top_signal": top_row.get("signal"),
        "top_signal_score": round(float(top_row["risk_score"]), 1),
        "top_technique": top_row.get("technique", "deviation"),
        "evaluation_timestamp": evaluation_timestamp,
    }


def aggregate_unit_health(
    system_results: list[dict],
    system_registry: list[dict],
) -> dict:
    """
    Aggregate system-level results into unit-level health assessment.

    Parameters:
        system_results: List of system health dicts
        system_registry: System metadata with criticality

    Returns:
        Unit health assessment dict.
    """
    if not system_results:
        return {
            "unit": "unknown",
            "overall_status": "InsufficientData",
            "priority_score": 0.0,
            "unit_score": 0.0,
            "n_anormal_systems": 0,
            "n_alerta_systems": 0,
            "top_risk_systems": [],
            "evaluation_timestamp": datetime.utcnow(),
        }

    unit = system_results[0]["unit"]

    # Build criticality map for systems
    sys_criticality = {}
    for s in system_registry:
        sys_criticality[s["name"]] = s.get("criticality", 2)

    # Count statuses
    critical_threshold = 2  # criticality ≤ 2 is "critical system"
    n_anormal_critical = 0
    n_anormal_other = 0
    n_alerta_critical = 0
    n_alerta_other = 0

    for sr in system_results:
        crit = sys_criticality.get(sr["system"], 3)
        is_critical = crit <= critical_threshold

        if sr["system_status"] == "Anormal":
            if is_critical:
                n_anormal_critical += 1
            else:
                n_anormal_other += 1
        elif sr["system_status"] == "Alerta":
            if is_critical:
                n_alerta_critical += 1
            else:
                n_alerta_other += 1

    # Unit score (average)
    unit_score = np.mean([sr["system_score"] for sr in system_results])

    # Priority score
    priority_score = (
        100 * n_anormal_critical
        + 50 * n_anormal_other
        + 20 * n_alerta_critical
        + 10 * n_alerta_other
        + unit_score
    )

    # Overall status
    total_anormal = n_anormal_critical + n_anormal_other
    if n_anormal_critical >= 1 or total_anormal >= 2:
        overall_status = "Anormal"
    elif (n_alerta_critical + n_alerta_other) >= 1:
        overall_status = "Alerta"
    else:
        overall_status = "Normal"

    # Top risk systems
    top_risk = sorted(system_results, key=lambda x: x["system_score"], reverse=True)
    top_risk_names = [s["system"] for s in top_risk[:3] if s["system_score"] > 0]

    return {
        "unit": unit,
        "overall_status": overall_status,
        "priority_score": round(priority_score, 1),
        "unit_score": round(unit_score, 1),
        "n_anormal_systems": total_anormal,
        "n_alerta_systems": n_alerta_critical + n_alerta_other,
        "top_risk_systems": top_risk_names,
        "evaluation_timestamp": system_results[0].get("evaluation_timestamp", datetime.utcnow()),
    }


def run_aggregation(
    technique_results: pd.DataFrame,
    signal_registry: dict,
    config: AggregationConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run full aggregation pipeline: System → Unit.

    Parameters:
        technique_results: Combined technique results (all techniques in one DF)
        signal_registry: Signal metadata
        config: Aggregation configuration

    Returns:
        (system_health_df, unit_health_df) tuple.
    """
    if technique_results.empty:
        return pd.DataFrame(), pd.DataFrame()

    units = technique_results["unit"].unique()
    systems_meta = signal_registry.get("systems", [])
    systems = [s["name"] for s in systems_meta] if systems_meta else technique_results["system"].unique().tolist()

    all_system_health = []
    all_unit_health = []

    for unit in units:
        unit_systems = []
        for system in systems:
            sh = aggregate_system_health(
                technique_results, signal_registry, system, unit, config
            )
            all_system_health.append(sh)
            unit_systems.append(sh)

        uh = aggregate_unit_health(unit_systems, systems_meta)
        all_unit_health.append(uh)

    system_df = pd.DataFrame(all_system_health)
    unit_df = pd.DataFrame(all_unit_health)

    # Sort units by priority
    if not unit_df.empty:
        unit_df.sort_values("priority_score", ascending=False, inplace=True)
        unit_df.reset_index(drop=True, inplace=True)

    logger.info(
        f"Aggregation complete: {len(system_df)} system assessments, "
        f"{len(unit_df)} unit assessments"
    )
    return system_df, unit_df
