"""
Event Analysis — Temporal pattern detection from deviation data.

Groups consecutive non-normal readings into discrete events with
both binary (duration-based) and weighted (severity-based) classification.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd
from tqdm import tqdm

from src.config.settings import (
    UNIT_COLNAME,
    TIME_COLNAME,
    EventConfig,
)

logger = logging.getLogger(__name__)


def identify_events(
    df_labeled: pd.DataFrame,
    feature: str,
) -> pd.DataFrame:
    """
    Identify consecutive non-normal events across all units for one feature.

    Parameters:
        df_labeled: DataFrame indexed by (Unit, Fecha) with risk_level_{feature} column
        feature: Signal name

    Returns:
        DataFrame with event groups and metadata.
    """
    risk_col = f"risk_level_{feature}"
    if risk_col not in df_labeled.columns:
        return pd.DataFrame()

    df = df_labeled[[risk_col]].copy()
    df = df.reset_index()

    # Binary non-normal indicator
    df["is_non_normal"] = ~df[risk_col].isin(["normal", "unknown"])

    all_events = []

    for unit, unit_df in df.groupby(UNIT_COLNAME):
        unit_df = unit_df.sort_values(TIME_COLNAME).reset_index(drop=True)

        if not unit_df["is_non_normal"].any():
            continue

        # Create event groups: new group when status changes or time gap > 1 min
        time_gap = unit_df[TIME_COLNAME].diff() > pd.Timedelta(minutes=1)
        status_change = unit_df["is_non_normal"] != unit_df["is_non_normal"].shift()
        unit_df["event_group"] = (status_change | (unit_df["is_non_normal"] & time_gap)).cumsum()

        events = unit_df[unit_df["is_non_normal"]].copy()
        events["unit"] = unit
        events["feature"] = feature
        all_events.append(events[[TIME_COLNAME, risk_col, "event_group", "unit", "feature"]])

    if not all_events:
        return pd.DataFrame()

    return pd.concat(all_events, ignore_index=True)


def calculate_event_metrics(
    events_df: pd.DataFrame,
    feature: str,
    config: EventConfig,
) -> pd.DataFrame:
    """
    Calculate binary and weighted event metrics.

    Parameters:
        events_df: Events from identify_events()
        feature: Signal name
        config: Event analysis configuration

    Returns:
        DataFrame with one row per event including both classification approaches.
    """
    if events_df.empty:
        return pd.DataFrame()

    risk_col = f"risk_level_{feature}"
    weights = config.severity_weights

    records = []
    for (unit, event_group), group in events_df.groupby(["unit", "event_group"]):
        duration = len(group)
        start_time = group[TIME_COLNAME].min()
        end_time = group[TIME_COLNAME].max()

        alert_min = (group[risk_col] == "alert").sum()
        anormal_min = (group[risk_col] == "anormal").sum()
        critical_min = (group[risk_col] == "critical").sum()

        total_points = (
            alert_min * weights["alert"]
            + anormal_min * weights["anormal"]
            + critical_min * weights["critical"]
        )

        # Binary classification
        if duration < config.spike_max_minutes:
            event_type_binary = "spike"
        elif duration < config.anomaly_max_minutes:
            event_type_binary = "anomaly"
        else:
            event_type_binary = "warning"

        # Weighted classification
        if total_points < config.spike_max_points:
            event_type_weighted = "spike"
        elif total_points < config.anomaly_max_points:
            event_type_weighted = "anomaly"
        else:
            event_type_weighted = "warning"

        records.append({
            "unit": unit,
            "feature": feature,
            "event_group": event_group,
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": duration,
            "total_severity_points": total_points,
            "event_type_binary": event_type_binary,
            "event_type_weighted": event_type_weighted,
            "max_severity": group[risk_col].map(
                {"critical": 3, "anormal": 2, "alert": 1}
            ).max(),
            "alert_minutes": alert_min,
            "anormal_minutes": anormal_min,
            "critical_minutes": critical_min,
        })

    return pd.DataFrame(records)


def run_event_analysis(
    df_labeled: pd.DataFrame,
    signal_registry: dict,
    config: EventConfig,
) -> pd.DataFrame:
    """
    Run event analysis across all features and units.

    Parameters:
        df_labeled: Deviation-labeled DataFrame (indexed by Unit, Fecha)
        signal_registry: Signal metadata
        config: Event configuration

    Returns:
        Combined event metrics DataFrame.
    """
    risk_cols = [c for c in df_labeled.columns if c.startswith("risk_level_")]
    features = [c.replace("risk_level_", "") for c in risk_cols]

    all_metrics = []

    for feature in tqdm(features, desc="Event analysis", unit="signal"):
        events = identify_events(df_labeled, feature)
        if events.empty:
            continue

        metrics = calculate_event_metrics(events, feature, config)
        if not metrics.empty:
            all_metrics.append(metrics)

    if not all_metrics:
        logger.info("No events detected across all features")
        return pd.DataFrame()

    result = pd.concat(all_metrics, ignore_index=True)
    result["execution_timestamp"] = datetime.utcnow()

    logger.info(
        f"Event analysis complete: {len(result)} events "
        f"({(result['event_type_weighted'] == 'warning').sum()} warnings)"
    )
    return result
